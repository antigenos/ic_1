// Exhaustive set-of-signals verification, independent of all SAT and orbit rules.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

using Signal = uint16_t;
using State = std::vector<Signal>;
struct Step { Signal a,b,out; };

static Signal normalized(unsigned t) {
    return static_cast<Signal>((t&1u) ? t^65535u : t);
}

static std::vector<Signal> images(Signal target) {
    std::array<int,4> p{0,1,2,3};
    std::vector<Signal> result;
    do {
        unsigned base[16]{};
        for (unsigned r=0;r<16;++r) for (unsigned j=0;j<4;++j)
            base[r] |= ((r>>p[j])&1u)<<j;
        for (unsigned phase=0;phase<16;++phase) {
            unsigned v=0;
            for (unsigned r=0;r<16;++r) v |= ((target>>(base[r]^phase))&1u)<<r;
            result.push_back(normalized(v));
        }
    } while (std::next_permutation(p.begin(),p.end()));
    std::sort(result.begin(),result.end());
    result.erase(std::unique(result.begin(),result.end()),result.end());
    return result;
}

struct SignalMap {
    std::array<std::array<Signal,256>,2> byte{};
    Signal apply(Signal x) const {
        return normalized(byte[0][x&255u] | byte[1][x>>8]);
    }
};

static std::vector<SignalMap> make_maps() {
    std::vector<SignalMap> maps;
    std::array<int,4> perm{0,1,2,3};
    do {
        for (unsigned ph=0;ph<16;++ph) {
            std::array<Signal,16> single{};
            for (unsigned i=0;i<16;++i) {
                unsigned source=ph;
                for (unsigned k=0;k<4;++k) source ^= ((i>>perm[k])&1u)<<k;
                single[source]=static_cast<Signal>(1u<<i);
            }
            SignalMap transform;
            for (int half=0;half<2;++half) for (unsigned v=1;v<256;++v)
                transform.byte[half][v]=transform.byte[half][v&(v-1)]|single[half*8+__builtin_ctz(v)];
            maps.push_back(transform);
        }
    } while (std::next_permutation(perm.begin(),perm.end()));
    return maps;
}

struct StateHash {
    size_t operator()(const State& s) const noexcept {
        size_t h=1469598103934665603ULL;
        for (Signal x : s) h=(h ^ x)*1099511628211ULL;
        return h;
    }
};

class Closure {
    const int limit;
    const size_t maximum_states;
    const bool orbit;
    std::vector<SignalMap> maps;
    std::vector<std::vector<Step>> solutions;
    std::vector<Step> path;
    std::unordered_set<State,StateHash> states;
    std::array<unsigned,32768> marks{};
    std::array<int,32768> best;
    std::array<int,32768> charge;
    unsigned stamp=0;
    const State inputs{0,0xaaaa,0xcccc,0xf0f0,0xff00};

    void visit(const State& s, int cost, const std::vector<unsigned>& symmetries) {
        if (!states.insert(s).second) return;
        if (states.size()>maximum_states) throw std::runtime_error("state limit reached, no certificate");
        unsigned here=++stamp;
        State available=inputs;
        std::vector<Step> next;
        available.insert(available.end(),s.begin(),s.end());
        for (Signal x : available) {
            marks[x/2]=here;
            best[x/2]=std::min(best[x/2],cost);
        }
        for (size_t i=0;i<available.size();++i) for (size_t j=0;j<i;++j) {
            unsigned a=available[i], b=available[j];
            for (unsigned x : {a & ~b,b & ~a,a ^ b,a & b,a | b}) {
                size_t index=x/2;
                if (marks[index]==here) continue;
                marks[index]=here;
                // Any legal output from these signals is free, even at the limit.
                Step step{static_cast<Signal>(a),static_cast<Signal>(b),static_cast<Signal>(x)};
                if (cost<best[index]) {
                    best[index]=cost;
                    if (!solutions.empty()) {
                        solutions[index]=path;
                        solutions[index].push_back(step);
                    }
                }
                if (!orbit || !s.empty() || x==0x8888 || x==0x6666) {
                    if (cost+charge[index]<=limit) next.push_back(step);
                }
            }
        }
        std::vector<unsigned> child_group;
        for (const Step& step : next) {
            Signal x=step.out;
            bool restricted=symmetries.size()>1;
            if (restricted) {
                bool keep=true;
                child_group.clear();
                for (unsigned m:symmetries) {
                    Signal y=maps[m].apply(x);
                    if (!s.empty() && y<x) { keep=false; break; }
                    if (y==x) child_group.push_back(m);
                }
                if (!keep) continue;
            }
            State child=s;
            child.insert(std::lower_bound(child.begin(),child.end(),x),x);
            path.push_back(step);
            visit(child,cost+charge[x/2],restricted ? child_group : symmetries);
            path.pop_back();
        }
    }

public:
    Closure(int cap,size_t max_states,bool reduced=false,bool witnesses=false,bool refine=false)
        : limit(cap), maximum_states(max_states),orbit(reduced),maps(refine ? make_maps() : std::vector<SignalMap>{}),
          solutions(witnesses ? 32768 : 0) {
        best.fill(limit+1);
        for (int i=0;i<32768;++i) {
            int ones=__builtin_popcount(static_cast<unsigned>(2*i));
            charge[i]=2*ones*(16-ones);
        }
    }
    void run() {
        std::vector<unsigned> group;
        for (unsigned i=0;i<maps.size();++i) group.push_back(i);
        visit({},0,group);
    }
    size_t total() const { return states.size(); }
    Signal representative(unsigned target) const {
        Signal original=normalized(target), chosen=original;
        if (orbit) for (Signal x:images(original))
            if (best[x/2]<best[chosen/2]) chosen=x;
        return chosen;
    }
    int minimum(Signal x) const {
        return best[x/2]<=limit ? best[x/2] : -1;
    }
    const std::vector<Step>& witness(Signal x) const { return solutions.at(x/2); }
};

#ifndef STUDY_CLOSURE_LIBRARY
int main(int argc,char **argv) {
    if (argc<3 || argc>4) return 1;
    try {
        int cap=std::stoi(argv[1]);
        size_t max_states=std::stoull(argv[2]);
        if (cap<0 || cap>1000 || !max_states || max_states>=UINT32_MAX) return 1;
        bool refine=argc==4 && std::string(argv[3])=="prefix";
        bool orbit=refine || (argc==4 && std::string(argv[3])=="orbit");
        bool witnesses=argc==4;
        if (witnesses && !orbit && std::string(argv[3])!="raw") return 1;
        Closure closure(cap,max_states,orbit,witnesses,refine);
        auto start=std::chrono::steady_clock::now();
        closure.run();
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::cout<<"C "<<cap<<" "<<closure.total()<<" "<<std::setprecision(12)<<seconds<<"\n";
        unsigned t;
        while (std::cin>>std::hex>>t) {
            if (t>65535) return 1;
            Signal image=closure.representative(t);
            int value=closure.minimum(image);
            std::cout<<std::hex<<t<<" "<<std::dec<<value;
            if (witnesses && value>=0) {
                std::cout<<" "<<std::hex<<image;
                for (auto s:closure.witness(image)) std::cout<<" "<<s.a<<","<<s.b<<","<<s.out;
            }
            std::cout<<"\n";
        }
    } catch (const std::exception& ex) {
        std::cerr<<ex.what()<<"\n";
        return 2;
    }
    return 0;
}
#endif
