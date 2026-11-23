// Exact cost-sublevel enumeration for essential-input Boolean functions.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using Word = std::uint64_t;
using Gate = std::array<int,3>;
int bits(Word x) { return __builtin_popcountll(x); }

struct Model {
    int n, rows, full;
    Word mask;
    std::vector<Word> inputs;
    explicit Model(int n): n(n), rows(1<<n), full((1<<n)-1),
        mask(rows==64 ? ~Word(0) : (Word(1)<<rows)-1), inputs(n) {
        for (int i=0;i<n;++i) for (int row=0;row<rows;++row)
            inputs[i] |= Word((row>>i)&1)<<row;
    }
    int support(Word t) const {
        int s=0;
        for (int i=0;i<n;++i)
            if (((t^(t>>(1<<i))) & ~inputs[i] & mask)!=0) s|=1<<i;
        return s;
    }
    int cost(int ones) const { return 2*ones*(rows-ones); }
    int floor(int support_size) const { return cost(rows>>support_size); }
    Word fold(Word t) const { return (t&1) ? mask^t : t; }
};

struct Orbit {
    const Model &model;
    std::vector<std::array<int,64>> permutations;
    std::unordered_map<Word,Word> representatives;
    explicit Orbit(const Model &m):model(m) {
        std::vector<int> p(m.n);
        std::iota(p.begin(),p.end(),0);
        do {
            std::array<int,64> positions{};
            for (int r=0;r<m.rows;++r) for (int i=0;i<m.n;++i)
                positions[r]|=((r>>i)&1)<<p[i];
            permutations.push_back(positions);
        } while (std::next_permutation(p.begin(),p.end()));
    }
    Word get(Word t) {
        auto it=representatives.find(t);
        if (it!=representatives.end()) return it->second;
        std::vector<Word> images;
        std::array<Word,64> translations{};
        Word least=model.mask;
        for (const auto &perm:permutations) {
            Word v=0;
            for (Word set=t;set;set&=set-1) v|=Word(1)<<perm[__builtin_ctzll(set)];
            translations[0]=v;
            for (int i=0;i<model.n;++i) {
                int length=1<<i;
                Word high=model.inputs[i];
                for (int j=0;j<length;++j) {
                    Word old=translations[j];
                    translations[length+j]=((old&high)>>length)|((old&~high)<<length);
                }
            }
            for (int j=0;j<model.rows;++j) {
                Word out=translations[j];
                least=std::min(least,std::min(out,out^model.mask));
                images.push_back(model.fold(out));
            }
        }
        for (Word v:images) representatives.emplace(v,least);
        return least;
    }
};

struct Partition {
    std::array<int,6> at{};
    int count, bound;
    explicit Partition(int n):count(n),bound(0) {
        for (int i=0;i<n;++i) at[i]=1<<i;
    }
    int block(int support) const { return at[__builtin_ctz(unsigned(support))]; }
    void join(int support,const Model &m) {
        int merged=0;
        for (int i=0;i<m.n;++i) if ((support>>i)&1) merged|=at[i];
        if (merged==block(support)) return;
        for (int i=0;i<m.n;++i) if ((merged>>i)&1) at[i]=merged;
        --count; // The two operands lie in at most two previous blocks.
        price(m);
    }
    void price(const Model &m) {
        std::array<int,6> sizes{};
        int k=0;
        for (int i=0;i<m.n;++i) if (__builtin_ctz(unsigned(at[i]))==i)
            sizes[k++]=bits(at[i]);
        if (k!=count) throw std::logic_error("component count");
        std::sort(sizes.begin(),sizes.end(),std::greater<int>());
        int size=sizes[0];
        bound=0;
        for (int i=1;i<k-1;++i) {
            size+=sizes[i];
            bound+=m.floor(size);
        }
    }
};

struct VectorHash {
    std::size_t operator()(const std::vector<Word> &key) const {
        Word h=0;
        for (Word v:key) h^=v+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);
        return h;
    }
};
struct Witness { int cost; Word truth; std::vector<Gate> gates; };
struct Search {
    Model model;
    Orbit orbit;
    int cap, mode;
    std::vector<Word> wires;
    std::vector<int> supports;
    std::vector<Gate> prefix;
    std::unordered_set<std::vector<Word>,VectorHash> seen;
    std::map<Word,Witness> results;
    Word visited=0, cut=0, forced=0, disallowed=0;
    Search(int n,int cap,int mode):model(n),orbit(model),cap(cap),mode(mode),wires(model.inputs) {
        for (int i=0;i<n;++i) supports.push_back(1<<i);
    }
    int positional(int depth) const {
        int price=0;
        for (int s=depth+2;s<model.n;++s) price+=model.floor(s);
        return price;
    }
    void record(Word v,int cost,Gate gate) {
        Word rep=orbit.get(v);
        auto it=results.find(rep);
        if (it!=results.end() && it->second.cost<=cost) return;
        Witness w{cost,v,prefix};
        w.gates.push_back(gate);
        results[rep]=std::move(w);
    }
    void visit(int cost,int introduced,const Partition &part) {
        int depth=int(prefix.size());
        int bound=positional(depth);
        if (mode>=1) bound=std::max(bound,part.bound);
        if (cost+bound>cap) { ++cut; return; }
        std::vector<Word> key(wires.begin()+model.n,wires.end());
        std::sort(key.begin(),key.end());
        if (!seen.insert(std::move(key)).second) return;
        ++visited;
        bool tree=mode==2 && part.count>=2 && cost+part.bound+model.floor(model.n)>cap;
        if (tree) ++forced;
        int length=int(wires.size());
        for (int b=1;b<length;++b) for (int a=0;a<b;++a) {
            // Introduce unseen inputs in order; any circuit can be relabelled this way.
            int next=introduced;
            if (a<model.n && a>=next) { if (a!=next) continue; ++next; }
            if (b<model.n && b>=next) { if (b!=next) continue; ++next; }
            int sa=supports[a], sb=supports[b];
            if (tree && (part.block(sa)==part.block(sb) ||
                    sa!=part.block(sa) || sb!=part.block(sb))) { ++disallowed; continue; }
            Word x=wires[a],y=wires[b];
            std::array<Word,5> out{x&y,x&~y,y&~x,x^y,x|y};
            constexpr int ops[]={8,2,4,6,14}; // Local encoding: bit index x+2*y.
            for (int op=0;op<5;++op) {
                Word v=out[op];
                if (!v || std::find(wires.begin(),wires.end(),v)!=wires.end()) continue;
                // The initial pair of literals has two NPN-inequivalent gate outputs.
                if (depth==0 && op!=0 && op!=3) continue;
                Gate g{a,b,ops[op]};
                int support=(sa&sb)==0 ? sa|sb : model.support(v);
                if (support==model.full) record(v,cost,g);
                int child=cost+model.cost(bits(v));
                if (child>cap || (tree && part.count==2)) continue;
                Partition merged=part;
                if (mode>=1) merged.join(support,model);
                prefix.push_back(g);
                supports.push_back(support);
                wires.push_back(v);
                visit(child,next,merged);
                wires.pop_back();
                supports.pop_back();
                prefix.pop_back();
            }
        }
    }
    void run() {
        Partition start(model.n);
        start.price(model);
        visit(0,0,start);
        for (const auto &[rep,w]:results) {
            std::cout<<"opt "<<std::hex<<rep<<" "<<w.truth<<std::dec<<" "<<w.cost;
            for (auto g:w.gates) std::cout<<" "<<g[0]<<","<<g[1]<<","<<g[2];
            std::cout<<"\n";
        }
        std::cout<<"stats "<<visited<<" "<<cut<<" "<<forced<<" "<<disallowed<<"\n";
    }
};
int main(int argc,char **argv) {
    if (argc!=4) return 2;
    int n=std::stoi(argv[1]), cap=std::stoi(argv[2]), mode=std::stoi(argv[3]);
    if (n<2 || n>6 || cap<0 || mode<0 || mode>2) return 2;
    Search search(n,cap,mode);
    search.run();
}
