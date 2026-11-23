// Shared weighted prefix enumeration for 3- or 4-input exact synthesis.
// TSV output includes the raw output and complete signal set for every witness.
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

using Wire = uint16_t;
using State = std::vector<Wire>;
constexpr int infinity = 1000000;
using Clock = std::chrono::steady_clock;

struct StateHash {
    size_t operator()(const State& s) const {
        size_t h = 1469598103934665603ULL;
        for (Wire v : s) h = (h ^ v) * 1099511628211ULL;
        return h;
    }
};

std::array<Wire, 5> combine(Wire a, Wire b) {
    return {Wire(a & b), Wire(a | b), Wire(a ^ b), Wire(a & ~b), Wire(b & ~a)};
}

struct Witness {
    int cost = infinity;
    Wire truth = 0;
    State state;
};

struct Search {
    int n, rows, count, cap;
    Wire mask;
    State pins;
    std::vector<State> images;
    State rep;
    std::vector<std::vector<int>> to_rep;
    std::vector<int> weights, profile, stamps;
    std::vector<Witness> best;
    int stamp = 0, boundary = infinity;
    uint64_t states = 0, edges = 0, crossings = 0;

    Search(int inputs, int budget):
        n(inputs), rows(1 << n), count(1 << rows), cap(budget), mask(count-1),
        rep(count, mask), to_rep(count), weights(count), profile(count, infinity),
        stamps(count), best(count) {
        std::vector<int> perm;
        for (int i=0; i<n; ++i) {
            unsigned p=0;
            for (int x=0; x<rows; ++x) p |= ((x >> i) & 1u) << x;
            pins.push_back(p);
            perm.push_back(i);
        }
        do {
            for (int phase=0; phase<rows; ++phase) {
                unsigned lut[2][256] = {};
                for (int x=0; x<rows; ++x) {
                    int y=phase;
                    for (int i=0; i<n; ++i) y ^= ((x >> i) & 1) << perm[i];
                    lut[y/8][1 << (y%8)] = 1u << x;
                }
                for (auto& tab : lut) for (unsigned b=1; b<256; ++b) {
                    unsigned low = b & -b;
                    tab[b] = tab[low] | tab[b ^ low];
                }
                State map(count/2);
                for (int v=0; v<count; v+=2) {
                    unsigned t=lut[0][v & 255] | lut[1][v >> 8];
                    map[v/2] = t ^ ((t & 1) ? mask : 0);
                    rep[v]=std::min(rep[v], map[v/2]);
                }
                images.push_back(std::move(map));
            }
        } while (std::next_permutation(perm.begin(),perm.end()));
        for (int v=0; v<count; v+=2) {
            weights[v]=price(std::popcount(unsigned(v)));
            for (unsigned g=0; g<images.size(); ++g)
                if (images[g][v/2]==rep[v]) to_rep[v].push_back(g);
        }
    }

    int price(int j) const { return 2*j*(rows-j); }

    State canonical(const State& child) const {
        Wire anchor=child.front();
        for (Wire v : child) {
            if (to_rep[v].size()<to_rep[anchor].size() ||
                (to_rep[v].size()==to_rep[anchor].size() && rep[v]<rep[anchor])) anchor=v;
        }
        State result, tmp(child.size());
        for (Wire v : child) if (rep[v]==rep[anchor]) {
            for (int g : to_rep[v]) {
                const auto& map=images[g];
                for (size_t i=0; i<child.size(); ++i) tmp[i]=map[child[i]/2];
                std::sort(tmp.begin(),tmp.end());
                if (result.empty() || tmp<result) result=tmp;
            }
        }
        return result;
    }

    void offer(Wire target, int cost, const State& s, Wire added=0) {
        auto& w=best[rep[target]];
        if (cost >= w.cost) return;
        w.cost=cost;
        w.truth=target;
        w.state=s;
        if (added) w.state.push_back(added);
    }

    void run() {
        using Level = std::unordered_set<State, StateHash>;
        Level current, next;
        current.insert(State{});
        offer(0,0,{});
        for (Wire p : pins) offer(p,0,{});
        while (!current.empty()) {
            for (const State& s : current) {
                ++states;
                State available=pins, choices;
                available.insert(available.end(),s.begin(),s.end());
                int cost=0;
                for (Wire a : s) cost+=weights[a];
                if (++stamp == std::numeric_limits<int>::max()) {
                    std::fill(stamps.begin(),stamps.end(),0);
                    stamp=1;
                }
                stamps[0]=stamp;
                for (Wire a : available) stamps[a]=stamp;
                for (size_t i=0; i<available.size(); ++i)
                    for (size_t j=0; j<i; ++j)
                        for (Wire v : combine(available[i],available[j])) {
                            offer(v,cost,s);
                            if (stamps[v]!=stamp) {
                                stamps[v]=stamp;
                                choices.push_back(v);
                            }
                        }
                int carry=infinity;
                for (Wire v : choices) {
                    ++edges;
                    int b=cost+weights[v];
                    if (b<=cap) {
                        State child=s;
                        child.push_back(v);
                        next.insert(canonical(child));
                    } else {
                        ++crossings;
                        carry=std::min(carry,b);
                        profile[rep[v]]=std::min(profile[rep[v]],b);
                        for (Wire p : available)
                            for (Wire f : combine(p,v)) offer(f,b,s,v);
                    }
                }
                boundary=std::min(boundary,carry);
                for (Wire p : available) profile[rep[p]]=std::min(profile[rep[p]],carry);
            }
            current.clear();
            current.swap(next);
        }
    }

    int partner(Wire p, Wire f) const {
        int minimum=infinity;
        auto zero=combine(p,0);
        auto one=combine(p,mask ^ 1);
        for (size_t i=0; i<zero.size(); ++i) {
            Wire need_one=zero[i]^f, need_zero=one[i]^f;
            if (need_one & need_zero) continue;
            int lo=std::max(1,std::popcount(need_one));
            int hi=std::popcount(unsigned(mask & ~1 & ~need_zero));
            if (lo<=hi) minimum=std::min({minimum,price(lo),price(hi)});
        }
        return minimum;
    }

    int unseen(Wire f) const {
        int a=std::popcount(f);
        a=std::min(a,rows-a);
        int lower=boundary+price(1)+price(std::max(1,a-1));
        for (int p=2; p<count; p+=2) {
            int base=profile[rep[p]];
            if (base+price(1)<lower)
                lower=std::min(lower,base+partner(p,f));
        }
        return lower;
    }

    void report(std::ostream& out, bool projected) const {
        out<<"meta "<<n<<" "<<cap<<" "<<states<<" "<<edges<<" "<<crossings<<" "<<boundary<<"\n";
        for (int p=2; p<count; p+=2) if (profile[p]<infinity)
            out<<"profile "<<p<<" "<<profile[p]<<"\n";
        for (int f=0; f<count; f+=2) if (rep[f]==f) {
            const auto& w=best[f];
            int floor=boundary+price(1);
            int lower=projected ? unseen(f) : floor;
            out<<"target "<<f<<" "<<w.cost<<" "<<std::min(w.cost,lower)<<" "
               <<std::min(w.cost,floor)<<" "<<w.truth;
            for (Wire s : w.state) out<<" "<<s;
            out<<"\n";
        }
    }
};

int main(int argc, char** argv) {
    if (argc!=5) { std::cerr<<"frontier n cap projected|uniform output.tsv\n"; return 2; }
    int n=std::stoi(argv[1]), cap=std::stoi(argv[2]);
    std::string mode=argv[3];
    if ((n!=3 && n!=4) || cap<0 || (mode!="projected" && mode!="uniform")) return 2;
    auto begin=Clock::now();
    Search search(n,cap);
    auto prepared=Clock::now();
    search.run();
    auto traversed=Clock::now();
    std::ofstream out(argv[4]);
    if (!out) return 3;
    search.report(out,mode=="projected");
    out.close();
    if (!out) return 3;
    auto done=Clock::now();
    auto seconds=[](auto a, auto b){return std::chrono::duration<double>(b-a).count();};
    std::cout<<"setup_s="<<seconds(begin,prepared)<<" search_s="<<seconds(prepared,traversed)
             <<" report_s="<<seconds(traversed,done)<<"\n";
}
