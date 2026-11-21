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
    std::unordered_set<State,StateHash> states;
    std::array<unsigned,32768> marks{};
    std::array<int,32768> best;
    std::array<int,32768> charge;
    unsigned stamp=0;
    const State inputs{0,0xaaaa,0xcccc,0xf0f0,0xff00};

    void visit(const State& s, int cost) {
        if (!states.insert(s).second) return;
        if (states.size()>maximum_states) throw std::runtime_error("state limit reached, no certificate");
        unsigned here=++stamp;
        State available=inputs, next;
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
                best[index]=std::min(best[index],cost);
                if (cost+charge[index]<=limit) next.push_back(static_cast<Signal>(x));
            }
        }
        for (Signal x : next) {
            State child=s;
            child.insert(std::lower_bound(child.begin(),child.end(),x),x);
            visit(child,cost+charge[x/2]);
        }
    }

public:
    Closure(int cap,size_t max_states) : limit(cap), maximum_states(max_states) {
        best.fill(limit+1);
        for (int i=0;i<32768;++i) {
            int ones=__builtin_popcount(static_cast<unsigned>(2*i));
            charge[i]=2*ones*(16-ones);
        }
    }
    void run() { visit({},0); }
    size_t total() const { return states.size(); }
    int minimum(unsigned target) const {
        unsigned x=(target&1u) ? target ^ 65535u : target;
        return best[x/2]<=limit ? best[x/2] : -1;
    }
};

int main(int argc,char **argv) {
    if (argc!=3) return 1;
    try {
        int cap=std::stoi(argv[1]);
        size_t max_states=std::stoull(argv[2]);
        if (cap<0 || cap>1000 || !max_states || max_states>=UINT32_MAX) return 1;
        Closure closure(cap,max_states);
        auto start=std::chrono::steady_clock::now();
        closure.run();
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::cout<<"C "<<cap<<" "<<closure.total()<<" "<<std::setprecision(12)<<seconds<<"\n";
        unsigned t;
        while (std::cin>>std::hex>>t) {
            if (t>65535) return 1;
            std::cout<<std::hex<<t<<" "<<std::dec<<closure.minimum(t)<<"\n";
        }
    } catch (const std::exception& ex) {
        std::cerr<<ex.what()<<"\n";
        return 2;
    }
}
