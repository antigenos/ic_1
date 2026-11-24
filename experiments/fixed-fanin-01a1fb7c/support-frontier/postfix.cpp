// Independent checker. Generate live DAGs as postfix expressions with references
// to a previously introduced input or completed gate. No state sets or component bounds.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>

using Truth = std::uint64_t;
struct Generator {
    int n, cap, rows, total=0, extra=0;
    std::vector<Truth> pi, wire, stack;
    std::vector<int> suffix;
    std::map<Truth,int> opt;
    std::uint64_t visits=0, finished=0;
    explicit Generator(int variables,int budget):n(variables),cap(budget),rows(1<<n),pi(n) {
        for (int r=0;r<rows;++r) for (int i=0;i<n;++i)
            if (r & (1<<i)) pi[i]|=Truth(1)<<r;
    }
    int charge(Truth v) const {
        int p=__builtin_popcountll(v);
        return 2*p*(rows-p);
    }
    bool essential(Truth v) const {
        for (int i=0;i<n;++i) {
            int step=1<<i;
            if (!((v^(v<<step))&pi[i])) return false;
        }
        return true;
    }
    void recurse(int inputs,int refs,int gates,int paid) {
        ++visits;
        if (paid+suffix[gates]>cap) return;
        if (stack.size()>=2) {
            Truth b=stack.back(); stack.pop_back();
            Truth a=stack.back(); stack.pop_back();
            if (a!=b) {
                Truth left=a&~b, right=b&~a, intersection=a&b;
                for (Truth v:{left,right,left|right,intersection,a|b}) {
                    if (!v || std::find(wire.begin(),wire.end(),v)!=wire.end()) continue;
                    if (gates+1==total) {
                        if (inputs==n && refs==extra && stack.empty() && essential(v)) {
                            ++finished;
                            auto it=opt.emplace(v,paid).first;
                            it->second=std::min(it->second,paid);
                        }
                    } else {
                        int next=paid+charge(v);
                        if (next+suffix[gates+1]>cap) continue;
                        wire.push_back(v); stack.push_back(v);
                        recurse(inputs,refs,gates+1,next);
                        stack.pop_back(); wire.pop_back();
                    }
                }
            }
            stack.push_back(a); stack.push_back(b);
        }
        if (inputs<n) {
            Truth v=pi[inputs];
            wire.push_back(v); stack.push_back(v);
            recurse(inputs+1,refs,gates,paid);
            stack.pop_back(); wire.pop_back();
        }
        if (refs<extra) {
            // Referring to an item does not introduce a new wire.
            std::size_t size=wire.size();
            for (std::size_t i=0;i<size;++i) {
                stack.push_back(wire[i]); recurse(inputs,refs+1,gates,paid); stack.pop_back();
            }
        }
    }
    void run() {
        for (total=n-1;;++total) {
            extra=total+1-n;
            suffix.assign(total,0);
            for (int i=total-2;i>=0;--i) {
                int p=rows>>std::min(n,i+2);
                suffix[i]=suffix[i+1]+2*p*(rows-p);
            }
            if (suffix[0]>cap) break;
            recurse(0,0,0,0);
        }
        for (auto [v,c]:opt) std::cout<<std::hex<<v<<std::dec<<" "<<c<<"\n";
        std::cout<<"stats "<<visits<<" "<<finished<<"\n";
    }
};
int main(int argc,char **argv) {
    if (argc!=3) return 2;
    int n=std::stoi(argv[1]),cap=std::stoi(argv[2]);
    if (n<2 || n>6 || cap<0) return 2;
    Generator generator(n,cap);
    generator.run();
}
