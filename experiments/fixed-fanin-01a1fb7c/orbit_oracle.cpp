// Independent breadth-first verification of activity bounds for the whole four-input family.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <limits>
#include <unordered_set>
#include <vector>

using Word = std::uint16_t;
constexpr int max_paid = 24;
using State = std::array<Word, max_paid>;
constexpr unsigned functions = 32768;
constexpr int symmetry_count = 24 * 16;
constexpr std::array<Word, 4> inputs{0xaaaa, 0xcccc, 0xf0f0, 0xff00};
std::array<std::array<Word, functions>, symmetry_count> images;
std::array<Word, functions> representative;
std::array<std::vector<unsigned short>, functions> to_representative;
std::array<int, functions> activity, minimum;
struct FinalState { State wires{}; int depth=0; Word out=0; };
std::array<FinalState, functions> final_states;

void offer(unsigned g,const State &s,int depth,int cost,bool keep)
{
    unsigned cls=representative[g>>1]>>1;
    if (cost>=minimum[cls]) return;
    minimum[cls]=cost;
    if (keep) final_states[cls]={s,depth,static_cast<Word>(g)};
}

Word normal(Word w) { return (w & 1u) ? static_cast<Word>(~w) : w; }

void build_group()
{
    representative.fill(65535);
    std::array<int, 4> perm{0,1,2,3};
    int index = 0;
    do {
        for (int phase = 0; phase < 16; ++phase, ++index) {
            std::array<int,16> dest{};
            for (int r = 0; r < 16; ++r) {
                int source = phase;
                for (int i=0; i<4; ++i) source ^= ((r >> perm[i]) & 1) << i;
                dest[source] = r;
            }
            std::array<Word, functions> raw{};
            for (unsigned x = 0; x < functions; ++x) {
                if (x) raw[x] = raw[x & (x-1)] | (1u << dest[1+__builtin_ctz(x)]);
                Word w = normal(raw[x]);
                images[index][x] = w;
                representative[x] = std::min(representative[x], w);
            }
        }
    } while (std::next_permutation(perm.begin(), perm.end()));
    for (unsigned x = 0; x < functions; ++x) {
        int a = __builtin_popcount(2*x);
        activity[x] = 2*a*(16-a);
        for (int i = 0; i < symmetry_count; ++i)
            if (images[i][x] == representative[x]) to_representative[x].push_back(i);
    }
}

State canonical(const State &s, int n)
{
    // Pick an invariant orbit, then consider every map sending any of its
    // members to the same representative. All equivalent sets have the same
    // candidate images. The smaller stabilizer reduces the number of sorts.
    std::size_t fewest = symmetry_count + 1;
    Word chosen = 65535;
    for (int i = 0; i < n; ++i) {
        unsigned x = s[i] >> 1;
        auto size = to_representative[x].size();
        if (size < fewest || (size == fewest && representative[x] < chosen)) {
            fewest = size;
            chosen = representative[x];
        }
    }
    State best{};
    best.fill(65535);
    for (int i = 0; i < n; ++i) {
        unsigned x = s[i] >> 1;
        if (representative[x] != chosen) continue;
        for (auto map : to_representative[x]) {
            State candidate{};
            for (int j = 0; j < n; ++j) candidate[j] = images[map][s[j] >> 1];
            std::sort(candidate.begin(), candidate.begin()+n);
            if (candidate < best) best = candidate;
        }
    }
    return best;
}

struct Hash {
    std::size_t operator()(const State &s) const {
        std::size_t h = 1469598103934665603ull;
        for (Word w : s) {
            if (!w) break;
            h = (h ^ w) * 1099511628211ull;
        }
        return h;
    }
};

struct Gate { int hi, lo, code; };

bool generate(Word goal, const std::vector<Word> &available, Gate &gate)
{
    constexpr std::array<int, 5> codes{4, 2, 6, 8, 14};
    for (int i=1; i<static_cast<int>(available.size()); ++i) {
        for (int j=0; j<i; ++j) {
            unsigned a=available[i], b=available[j];
            std::array<unsigned,5> outs{a & ~b, b & ~a, a ^ b, a & b, a | b};
            for (int k=0; k<5; ++k) if (outs[k]==goal) {
                gate={i,j,codes[k]};
                return true;
            }
        }
    }
    return false;
}

void emit_circuit(unsigned target, int value)
{
    Word goal=normal(target);
    std::vector<Word> available(inputs.begin(),inputs.end());
    std::vector<Gate> gates;
    int direct = -2;
    if (value >= 0) {
        auto it=std::find(available.begin(),available.end(),goal);
        if (!goal) direct=-1;
        else if (it!=available.end()) direct=static_cast<int>(it-available.begin());
        else {
            const auto &seed=final_states[representative[goal>>1]>>1];
            int map=0;
            while (map<symmetry_count && images[map][seed.out>>1]!=goal) ++map;
            if (map==symmetry_count) throw std::logic_error("Missing output transformation");
            std::vector<Word> pending;
            for (int i=0;i<seed.depth;++i) pending.push_back(images[map][seed.wires[i]>>1]);
            Gate g{};
            while (!pending.empty()) {
                auto ready=std::find_if(pending.begin(),pending.end(),[&](Word w){return generate(w,available,g);});
                if (ready==pending.end()) throw std::logic_error("Unreachable transformed state");
                available.push_back(*ready);
                gates.push_back(g);
                pending.erase(ready);
            }
            if (!generate(goal,available,g)) throw std::logic_error("Missing final operation");
            gates.push_back(g);
        }
    }
    std::cout << "{\"truth\":\"" << std::hex << std::setw(4) << std::setfill('0') << target
              << "\",\"activity\":" << std::dec << value << ",\"complement\":" << (target&1)
              << ",\"direct\":" << direct << ",\"gates\":[";
    for (std::size_t i=0;i<gates.size();++i) {
        const auto &g=gates[i];
        if (i) std::cout << ",";
        std::cout << "[" << g.hi << "," << g.lo << "," << g.code << "]";
    }
    std::cout << "]}\n";
}

int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    bool circuits=false, terminal=false;
    std::size_t layer_limit=2000000;
    for (int i=2;i<argc;++i) {
        std::string opt(argv[i]);
        if (opt=="--circuits") circuits=true;
        else if (opt=="--terminal") terminal=true;
        else if (opt.rfind("--layer-limit=",0)==0) {
            layer_limit=std::stoul(opt.substr(14));
            if (!layer_limit) return 2;
        }
        else return 2;
    }
    int cap = std::stoi(argv[1]);
    if (cap < 0 || cap > 30*max_paid) return 2;
    build_group();
    minimum.fill(std::numeric_limits<int>::max());
    minimum[0] = 0;
    minimum[representative[inputs[0] >> 1] >> 1] = 0;
    std::unordered_set<State, Hash> layer{State{}};
    std::array<unsigned, functions> marked{};
    unsigned stamp = 0;
    std::cout << "layers";
    for (int depth = 0; !layer.empty(); ++depth) {
        std::cout << " " << layer.size() << std::flush;
        std::unordered_set<State, Hash> next;
        for (const State &s : layer) {
            ++stamp;
            std::array<Word, 4+max_paid> wires{};
            std::copy(inputs.begin(),inputs.end(),wires.begin());
            std::copy_n(s.begin(),depth,wires.begin()+4);
            int paid = 0;
            for (int i = 0; i < depth; ++i) paid += activity[s[i] >> 1];
            for (int i=1; i<depth+4; ++i) for (int j=0; j<i; ++j) {
                unsigned a=wires[i], b=wires[j];
                for (unsigned g : {a & ~b, b & ~a, a ^ b, a & b, a | b}) {
                    unsigned x = g >> 1;
                    if (marked[x] == stamp) continue;
                    marked[x] = stamp;
                    offer(g,s,depth,paid,circuits);
                    if (!g || depth == max_paid || paid + activity[x] > cap) continue;
                    if (std::find(inputs.begin(),inputs.end(),g) != inputs.end() ||
                        std::binary_search(s.begin(),s.begin()+depth,g)) continue;
                    State child = s;
                    child[depth] = g;
                    int new_cost=paid+activity[x];
                    if (terminal && new_cost+30>cap) {
                        // No further nonconstant paid gate can fit. Every new
                        // free output must join g to an existing signal.
                        for (int k=0;k<depth+4;++k) {
                            unsigned h=wires[k];
                            for (unsigned out : {g & ~h, h & ~g, g ^ h, g & h, g | h})
                                offer(out,child,depth+1,new_cost,circuits);
                        }
                        continue;
                    }
                    next.insert(canonical(child,depth+1));
                    if (next.size() > layer_limit) {
                        std::cerr << " layer size limit; proof incomplete\n";
                        return 3;
                    }
                }
            }
        }
        layer.swap(next);
    }
    std::cout << "\n";
    unsigned target;
    while (std::cin >> std::hex >> target) {
        if (target > 65535) return 2;
        int value = minimum[representative[normal(target) >> 1] >> 1];
        if (circuits) emit_circuit(target, value <= cap ? value : -1);
        else std::cout << std::hex << target << " " << std::dec << (value <= cap ? value : -1) << "\n";
    }
}
