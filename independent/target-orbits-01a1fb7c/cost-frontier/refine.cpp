// Complete the shared library using the projected residual test on each branch.
#define DIRECT_LIBRARY
#include "direct.cpp"

struct Completion {
    Direct engine;
    std::vector<int> lower;
    State classes;
    std::vector<int> operand_ceiling;
    int two_ceiling=-1;

    Completion(int n,int seed): engine(n,seed), lower(engine.count), operand_ceiling(engine.count,-1) {
        for (int f=0; f<engine.count; f+=2) if (engine.rep[f]==f) classes.push_back(f);
        engine.run();
        for (Wire f : classes) lower[f]=std::min(engine.best[f].cost,engine.unseen(f));
    }

    int open_count() const {
        int result=0;
        for (Wire f : classes) result+=lower[f]<engine.best[f].cost;
        return result;
    }

    int next_budget() const {
        int largest=0, largest_open=0;
        bool missing=false;
        for (Wire f : classes) {
            int upper=engine.best[f].cost;
            if (upper<infinity) largest=std::max(largest,upper);
            if (lower[f]>=upper) continue;
            if (upper==infinity) missing=true;
            else largest_open=std::max(largest_open,upper);
        }
        return missing ? largest+engine.price(1) : largest_open;
    }

    int set_limits(int budget, bool project) {
        std::vector<int> cutoff(engine.count,-infinity);
        int overall=-1;
        two_ceiling=-1;
        std::fill(operand_ceiling.begin(),operand_ceiling.end(),-1);
        for (Wire f : classes) {
            int b=std::min(budget,engine.best[f].cost-1);
            if (lower[f]>b) continue;
            cutoff[f]=b;
            overall=std::max(overall,b);
            int a=std::popcount(f);
            a=std::min(a,engine.rows-a);
            int pair_cost=engine.price(1)+engine.price(std::max(1,a-1));
            two_ceiling=std::max(two_ceiling,b-pair_cost);
        }
        if (!project || overall<0) return overall;
        for (Wire p : classes) {
            if (!p) continue;
            int limit=-1;
            for (int q=2; q<engine.count; q+=2) {
                int b=-infinity;
                for (Wire f : combine(p,Wire(q))) b=std::max(b,cutoff[engine.rep[f]]);
                limit=std::max(limit,b-engine.weights[q]);
            }
            operand_ceiling[p]=limit;
        }
        return overall;
    }

    void finish(int budget,bool project) {
        int search_budget=set_limits(budget,project);
        if (search_budget>=0) {
            engine.cap=search_budget;
            engine.states=engine.edges=engine.rejected=engine.fringe=engine.terminal_cuts=0;
            engine.direct(project ? &operand_ceiling : nullptr,two_ceiling);
        }
        for (Wire f : classes)
            lower[f]=std::min(engine.best[f].cost,std::max(lower[f],budget+1));
    }
};

#ifndef REFINE_LIBRARY
int main(int argc,char** argv) {
    if (argc!=6) { std::cerr<<"refine n seed auto|budget projected|uniform output.tsv\n"; return 2; }
    int n=std::stoi(argv[1]), seed=std::stoi(argv[2]);
    bool automatic=std::string(argv[3])=="auto", project=std::string(argv[4])=="projected";
    if ((n!=3 && n!=4) || seed<0 || (!project && std::string(argv[4])!="uniform")) return 2;
    auto start=Clock::now();
    Completion run(n,seed);
    auto seeded=Clock::now();
    auto seconds=[](auto a,auto b){return std::chrono::duration<double>(b-a).count();};
    std::cout<<"seed="<<seed<<" open="<<run.open_count()<<" seed_s="<<seconds(start,seeded)<<"\n";
    int budget=automatic ? run.next_budget() : std::stoi(argv[3]);
    if (budget<0 || budget>=infinity-1) return 2;
    while (run.open_count()) {
        auto begin=Clock::now();
        run.finish(budget,project);
        std::cout<<"budget="<<budget<<" open="<<run.open_count()<<" states="<<run.engine.states
                 <<" edges="<<run.engine.edges<<" projected_terminal="<<run.engine.terminal_cuts
                 <<" end_pruned="<<run.engine.rejected<<" search_s="<<seconds(begin,Clock::now())<<"\n";
        if (!automatic || !run.open_count()) break;
        budget=std::max(budget+run.engine.price(1),run.next_budget());
    }
    std::ofstream out(argv[5]);
    if (!out) return 3;
    out<<"meta "<<n<<" "<<budget<<" "<<run.engine.states<<" "<<run.engine.edges<<" "<<run.engine.fringe<<" "<<budget+1<<"\n";
    for (Wire f : run.classes) {
        const auto& w=run.engine.best[f];
        out<<"target "<<f<<" "<<w.cost<<" "<<run.lower[f]<<" "<<run.lower[f]<<" "<<w.truth;
        for (Wire v : w.state) out<<" "<<v;
        out<<"\n";
    }
    out.close();
    std::cout<<"elapsed_s="<<seconds(start,Clock::now())<<"\n";
    return out ? 0 : 3;
}
#endif
