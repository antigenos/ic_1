// Cold proof interface for a single author CLI invocation.
#define STUDY_CLOSURE_LIBRARY
#include "cost_closure.cpp"
#include <cstdio>

extern "C" int study_four_bound(unsigned target, int *gates)
{
    int lower=0;
    *gates=0;
    try {
        for (int cap : {302,366,440}) {
            Closure closure(cap,6000000,true,true);
            closure.run();
            Signal image=closure.representative(target);
            int value=closure.minimum(image);
            std::printf("CLOSURE cap=%d states=%zu score=%d\n",cap,closure.total(),value);
            if (value>=0) {
                *gates=static_cast<int>(closure.witness(image).size());
                return value;
            }
            lower=cap+2;
        }
    } catch (const std::exception& e) {
        std::printf("CLOSURE fallback=%s lower=%d\n",e.what(),lower);
    }
    return lower;
}

static bool restore_gates(const std::vector<Step>& steps, Signal image, Signal wanted, int (*out)[3]) {
    auto maps=make_maps();
    auto it=std::find_if(maps.begin(),maps.end(),[&](const SignalMap& m){return m.apply(image)==wanted;});
    if (it==maps.end() || steps.size()>40 || steps.size()<2) return false;
    State signals{0xaaaa,0xcccc,0xf0f0,0xff00};
    const int ops[]={2,4,6,8,14};
    for (size_t i=0;i<steps.size();++i) {
        const Step& step=steps[i];
        unsigned value=it->apply(step.out);
        auto a=std::find(signals.begin(),signals.end(),it->apply(step.a));
        auto b=std::find(signals.begin(),signals.end(),it->apply(step.b));
        if (a==signals.end() || b==signals.end() || a==b) return false;
        auto high=std::max(a,b), low=std::min(a,b);
        unsigned h=*high,l=*low;
        unsigned functions[]={h&~l,l&~h,h^l,h&l,h|l};
        auto op=std::find(functions,functions+5,value);
        if (op==functions+5) return false;
        out[i][0]=static_cast<int>(high-signals.begin()); out[i][1]=static_cast<int>(low-signals.begin());
        out[i][2]=ops[op-functions];
        signals.push_back(static_cast<Signal>(value));
    }
    return signals.back()==wanted;
}

extern "C" int study_extended_bound(unsigned target,int limit,int *gates,int (*out)[3]) {
    int lower=0;
    *gates=0;
    try {
        for (int cap:{302,366,440,500,560}) {
            if (cap>limit) break;
            Closure closure(cap,9000000,true,true,true);
            closure.run();
            Signal image=closure.representative(target);
            int answer=closure.minimum(image);
            std::printf("PREFIX cap=%d states=%zu score=%d\n",cap,closure.total(),answer);
            std::fflush(stdout);
            if (answer>=0) {
                const auto& path=closure.witness(image);
                if (restore_gates(path,image,normalized(target),out)) *gates=static_cast<int>(path.size());
                return answer;
            }
            lower=cap+2;
        }
    } catch (const std::exception& e) {
        std::printf("PREFIX fallback=%s lower=%d\n",e.what(),lower);
    }
    return lower;
}
