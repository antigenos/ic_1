// Compiled into the same ABC process as the pinned pexact plugin.
#define REFINE_LIBRARY
#include "refine.cpp"
#include <cstdlib>
#include <memory>

extern "C" int frontier_bound(unsigned raw, int cap, int projected,
                              unsigned short* ordered, int capacity, int* length) {
    *length=-1;
    if (cap<0 || raw>=65536 || (raw & 1u)) return 0;
    for (unsigned i=0; i<4; ++i) {
        bool essential=false;
        for (unsigned x=0; x<16; ++x)
            essential |= ((raw >> x) ^ (raw >> (x ^ (1u<<i)))) & 1;
        if (!essential) return 0;
    }
    try {
        static std::unique_ptr<Search> shared;
        static std::unique_ptr<Completion> completed;
        static int saved_seed=-1, saved_projection=-1;
        const char* flag=std::getenv("PEXACT_FRONTIER_COMPLETE");
        bool full=flag && std::string(flag)=="1";
        if (full) {
            if (!completed || saved_seed!=cap || saved_projection!=projected) {
                auto ready=std::make_unique<Completion>(4,cap);
                int budget=ready->next_budget();
                while (ready->open_count()) {
                    ready->finish(budget,projected!=0);
                    if (ready->open_count())
                        budget=std::max(budget+ready->engine.price(1),ready->next_budget());
                }
                completed=std::move(ready);
                saved_seed=cap;
                saved_projection=projected;
            }
        } else if (!shared || shared->cap!=cap) {
            auto ready=std::make_unique<Search>(4,cap);
            ready->run();
            shared=std::move(ready);
        }
        const Search& lib=full ? static_cast<const Search&>(completed->engine) : *shared;
        Wire f=lib.rep[raw];
        const auto& witness=lib.best[f];
        int lower=full ? completed->lower[f] :
            std::min(witness.cost, projected ? lib.unseen(f) : lib.boundary+lib.price(1));
        if (lower!=witness.cost || lower>=infinity || int(witness.state.size())>capacity)
            return lower;
        // Under a signed variable transformation primary pins normalize back to pins.
        const auto transform=std::find_if(lib.images.begin(),lib.images.end(),
                                         [&](const State& map){return map[witness.truth/2]==raw;});
        if (transform==lib.images.end()) throw std::logic_error("no witness orientation");
        State pending, available=lib.pins;
        for (Wire w : witness.state) pending.push_back((*transform)[w/2]);
        int placed=0;
        while (!pending.empty()) {
            auto found=pending.end();
            for (size_t i=1; i<available.size() && found==pending.end(); ++i)
                for (size_t j=0; j<i && found==pending.end(); ++j)
                    for (Wire v : combine(available[i],available[j])) {
                        found=std::find(pending.begin(),pending.end(),v);
                        if (found!=pending.end()) break;
                    }
            if (found==pending.end()) throw std::logic_error("unreachable internal wire");
            available.push_back(*found);
            ordered[placed++]=*found;
            pending.erase(found);
        }
        *length=placed;
        return lower;
    } catch (const std::exception& e) {
        std::cerr<<"frontier fallback: "<<e.what()<<"\n";
        return 0;
    }
}
