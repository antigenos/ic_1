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
