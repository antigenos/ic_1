// Independent cost-ordered checker for the four-input minimum switching library.
#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <unordered_set>
#include <vector>

using Signal = std::uint16_t;
constexpr unsigned mask = 65535;
constexpr int words = 32768;
constexpr int group_size = 384;
constexpr int width = 24;
using Key = std::array<Signal,width>;

Signal fold(unsigned value) { return (value & 32768) ? (value ^ mask) : value; }

struct Tables {
    std::array<Signal, group_size> image[words];
    std::array<Signal,words> orbit{};
    std::array<unsigned char,words> weight{};
    std::vector<unsigned short> maximal[words];
    std::array<Signal,4> inputs{};

    Tables() {
        for (int i=0;i<4;++i) {
            unsigned tt=0;
            for (int r=0;r<16;++r) tt |= ((r>>i)&1u)<<r;
            inputs[i]=fold(tt);
        }
        std::array<int,4> perm{0,1,2,3};
        int g=0;
        do {
            for (int phase=0;phase<16;++phase,++g) {
                std::array<unsigned,16> point{};
                for (int old=0;old<16;++old) {
                    int row=phase;
                    for (int i=0;i<4;++i) row ^= ((old>>i)&1)<<perm[i];
                    point[old]=1u<<row;
                }
                unsigned low[256]{}, high[256]{};
                for (int byte=0;byte<256;++byte) for (int bit=0;bit<8;++bit) {
                    if ((byte>>bit)&1) { low[byte]|=point[bit]; high[byte]|=point[8+bit]; }
                }
                for (int v=0;v<words;++v) {
                    Signal w=fold(low[v&255] | high[v>>8]);
                    image[v][g]=w;
                    orbit[v]=std::max(orbit[v],w);
                }
            }
        } while (std::next_permutation(perm.begin(),perm.end()));
        if (g!=group_size) throw std::logic_error("invalid group");
        for (int v=0;v<words;++v) {
            int ones=__builtin_popcount((unsigned)v);
            weight[v]=2*ones*(16-ones);
            for (int i=0;i<group_size;++i) if (image[v][i]==orbit[v]) maximal[v].push_back(i);
        }
    }

    Key key(const Key &s,int size) const {
        // Maximize a member of the least symmetric orbit, then maximize the
        // entire descending wire list over all its possible anchor members.
        Signal anchor=s[0];
        for (int k=1;k<size;++k) {
            Signal v=s[k];
            if (maximal[v].size()<maximal[anchor].size() ||
                (maximal[v].size()==maximal[anchor].size() && orbit[v]>orbit[anchor])) anchor=v;
        }
        Key best{};
        for (int k=0;k<size;++k) if (orbit[s[k]]==orbit[anchor]) {
            for (int g:maximal[s[k]]) {
                Key label{};
                for (int i=0;i<size;++i) label[i]=image[s[i]][g];
                std::sort(label.begin(),label.begin()+size,std::greater<Signal>());
                if (best<label) best=label;
            }
        }
        return best;
    }
};

struct Hash {
    std::size_t operator()(const Key &k) const {
        std::uint64_t h=0;
        for (Signal v:k) {
            if (!v) break;
            h=(h*0x9e3779b185ebca87ULL) ^ (v+0x165667b19e3779f9ULL);
        }
        return h^(h>>31);
    }
};

std::array<Signal,5> outputs(Signal a,Signal b) {
    Signal both=a&b, only_a=a^both, only_b=b^both;
    return {both,only_a,only_b,Signal(only_a|only_b),Signal(a|b)};
}

int main(int argc,char **argv) {
    if (argc!=2) return 2;
    int cap=std::stoi(argv[1]);
    if (cap<30 || cap>30*width) return 2;
    static const Tables tbl;
    std::vector<std::unordered_set<Key,Hash>> queue(cap+1);
    std::array<int,words> price{};
    price.fill(cap+1);
    price[0]=0;
    for (Signal pi:tbl.inputs) price[tbl.orbit[pi]]=0;
    std::vector<std::array<std::uint64_t,width+1>> visits(cap+1);
    std::array<std::uint64_t,words> seen{};
    std::uint64_t serial=0;
    queue[0].insert(Key{});
    for (int cost=0;cost<=cap;++cost) {
        std::unordered_set<Key,Hash> current;
        current.swap(queue[cost]);
        for (const Key &s:current) {
            ++serial;
            int size=std::find(s.begin(),s.end(),0)-s.begin();
            ++visits[cost][size];
            std::array<Signal,width+4> wire{};
            std::copy_n(s.begin(),size,wire.begin());
            std::copy(tbl.inputs.begin(),tbl.inputs.end(),wire.begin()+size);
            for (int i=0;i<size+4;++i) for (int j=0;j<i;++j) {
                for (Signal v:outputs(wire[i],wire[j])) {
                    if (seen[v]==serial) continue;
                    seen[v]=serial;
                    int &value=price[tbl.orbit[v]];
                    value=std::min(value,cost);
                    int child_cost=cost+tbl.weight[v];
                    if (!v || child_cost>cap || std::find(wire.begin(),wire.begin()+size+4,v)!=wire.begin()+size+4) continue;
                    if (child_cost>cap-30) {
                        for (int k=0;k<size+4;++k) for (Signal out:outputs(wire[k],v)) {
                            int &terminal=price[tbl.orbit[out]];
                            terminal=std::min(terminal,child_cost);
                        }
                    } else {
                        if (size>=width) throw std::logic_error("wire capacity exceeded");
                        Key larger=s;
                        larger[size]=v;
                        queue[child_cost].insert(tbl.key(larger,size+1));
                    }
                }
            }
        }
    }
    for (int c=0;c<=cap;++c) for (int n=0;n<=width;++n) {
        if (visits[c][n]) std::cout<<"states "<<c<<" "<<n<<" "<<visits[c][n]<<"\n";
    }
    unsigned t;
    while (std::cin>>std::hex>>t) {
        if (t>mask) return 2;
        int minimum=price[tbl.orbit[fold(t)]];
        std::cout<<"opt "<<std::hex<<t<<std::dec<<" "<<(minimum>cap ? -1 : minimum)<<"\n";
    }
    return 0;
}
