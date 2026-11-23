// Direct budget-limited control adapted from Goucher's removable ends, with
// exact DATE activities. All answers at or below the supplied budget are exact.
#define FRONTIER_LIBRARY
#include "frontier.cpp"

using Bits = uint64_t;
using Recipes = std::vector<std::vector<Bits>>;

// Removing wire i leaves an attainable set iff repeated forward closure
// starting with only the inputs reaches every other wire.
Bits removable(const Recipes& recipes) {
    Bits all=(Bits(1)<<recipes.size())-1, ends=0;
    for (size_t i=0; i<recipes.size(); ++i) {
        Bits remaining=all^(Bits(1)<<i), known=0, previous;
        do {
            previous=known;
            for (size_t j=0; j<recipes.size(); ++j) {
                Bits bit=Bits(1)<<j;
                if (!(remaining & ~known & bit)) continue;
                for (Bits req : recipes[j]) if (!(req & ~known)) {
                    known |= bit;
                    break;
                }
            }
        } while (known!=previous && known!=remaining);
        if (known==remaining) ends |= Bits(1)<<i;
    }
    return ends;
}

struct Direct : Search {
    using Search::Search;
    uint64_t rejected=0, fringe=0;

    void direct() {
        using Level=std::unordered_set<State, StateHash>;
        Level level, next;
        level.insert(State{});
        offer(0,0,{});
        for (Wire v : pins) offer(v,0,{});
        std::vector<int> index(count,-1);
        while (!level.empty()) {
            for (const State& s : level) {
                ++states;
                if (s.size()>=63) throw std::runtime_error("control bitset capacity");
                State a=pins;
                a.insert(a.end(),s.begin(),s.end());
                int cost=0;
                for (size_t i=0; i<s.size(); ++i) {
                    index[s[i]]=i;
                    cost+=weights[s[i]];
                }
                int remaining=(cap-cost)/price(1);
                // End pruning is necessary only if even consuming all available
                // future gates would leave some end alive. Near the budget,
                // computing the same ends also cuts the candidate fringe.
                Bits ends=0;
                if (s.size()>=2 && int(s.size())>remaining) {
                    Recipes recipes(s.size());
                    for (size_t i=1; i<a.size(); ++i) for (size_t j=0; j<i; ++j) {
                        Bits inputs=0;
                        if (i>=pins.size()) inputs|=Bits(1)<<(i-pins.size());
                        if (j>=pins.size()) inputs|=Bits(1)<<(j-pins.size());
                        for (Wire v : combine(a[i],a[j])) {
                            int k=index[v];
                            if (k>=0 && !(inputs & (Bits(1)<<k))) recipes[k].push_back(inputs);
                        }
                    }
                    ends=removable(recipes);
                }
                for (Wire v : s) index[v]=-1;
                if (std::popcount(ends)>remaining+2) { ++rejected; continue; }
                if (++stamp==std::numeric_limits<int>::max()) {
                    std::fill(stamps.begin(),stamps.end(),0);
                    stamp=1;
                }
                stamps[0]=stamp;
                for (Wire v : a) stamps[v]=stamp;
                State choices;
                for (size_t i=1; i<a.size(); ++i) for (size_t j=0; j<i; ++j) {
                    Bits operands=0;
                    if (i>=pins.size()) operands|=Bits(1)<<(i-pins.size());
                    if (j>=pins.size()) operands|=Bits(1)<<(j-pins.size());
                    int pending=std::popcount(ends & ~operands);
                    for (Wire v : combine(a[i],a[j])) {
                        if (!pending) offer(v,cost,s);
                        int b=cost+weights[v];
                        if (b>cap || stamps[v]==stamp) continue;
                        // Existing removable ends other than these two operands
                        // remain removable; the freshly appended wire is one more.
                        if (pending+1>(cap-b)/price(1)+2) continue;
                        stamps[v]=stamp;
                        choices.push_back(v);
                    }
                }
                for (Wire v : choices) {
                    ++edges;
                    int b=cost+weights[v];
                    if (b+price(1)>cap) {
                        ++fringe;
                        for (Wire x : a) for (Wire f : combine(x,v)) offer(f,b,s,v);
                    } else {
                        State child=s;
                        child.push_back(v);
                        next.insert(canonical(child));
                    }
                }
            }
            level.clear();
            level.swap(next);
        }
    }
};

int main(int argc,char** argv) {
    if (argc!=4) return 2;
    int n=std::stoi(argv[1]), cap=std::stoi(argv[2]);
    if ((n!=3 && n!=4) || cap<0) return 2;
    auto start=Clock::now();
    Direct d(n,cap);
    d.direct();
    std::ofstream out(argv[3]);
    if (!out) return 3;
    out<<"meta "<<n<<" "<<cap<<" "<<d.states<<" "<<d.edges<<" "<<d.fringe<<" "<<cap+1<<"\n";
    for (int f=0; f<d.count; f+=2) if (d.rep[f]==f) {
        auto& w=d.best[f];
        int lower=std::min(w.cost,cap+1);
        out<<"target "<<f<<" "<<w.cost<<" "<<lower<<" "<<lower<<" "<<w.truth;
        for (Wire v : w.state) out<<" "<<v;
        out<<"\n";
    }
    out.close();
    std::cout<<"removed_states="<<d.rejected<<" elapsed_s="
             <<std::chrono::duration<double>(Clock::now()-start).count()<<"\n";
    return out ? 0 : 3;
}
