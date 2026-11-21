/* Independent differential check against the author's complete local evaluator. */
#include <stdio.h>
#include "joint_relation.h"
#include "interval.h"

static unsigned seed = 17319;
static unsigned draw(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

static int verify(int n, unsigned t, unsigned h, unsigned ops, unsigned z, unsigned o,
                  unsigned domain, int cap)
{
    unsigned full = (1u<<n)-1;
    unsigned zeros[2] = {z,full^h}, ones[2] = {o,h}, domains[2] = {domain,1u<<(n/2)};
    FfFixedOperand p = ff_operand(n,t,h);
    P9JointResult a = ff_interval(&p,n,ops,z,o,domain,cap), ref;
    if (p9_joint_support(n,t,ops,zeros,ones,domains,cap,1,&ref)) return 0;
    for (int k = 0; k < 2; ++k)
        if (a.supported[k] != ref.supported[k] || a.without_budget[k] != ref.without_budget[k]) {
            fprintf(stderr,"Mismatch rows=%d target=%x h=%x ops=%x z=%x o=%x d=%x cap=%d\n",
                    n,t,h,ops,z,o,domain,cap);
            return 0;
        }
    return 1;
}

int main(void)
{
    unsigned long long exhaustive = 0, sampled = 0;
    const int caps[] = {-1,0,5,6,7,8,128,32767};
    ff_width_tables(4);
    for (unsigned t=0; t<16; t+=2) for (int i=0;i<2;++i)
        for (unsigned ops=0;ops<32;++ops) for (unsigned d=0;d<8;d+=2)
            for (int trit=0;trit<27;++trit) {
                unsigned z=1,o=0;
                int a=trit;
                for (int r=1;r<4;++r,a/=3) {
                    if (a%3==1) z |= 1u<<r;
                    if (a%3==2) o |= 1u<<r;
                }
                for (int c=0;c<8;++c) {
                    if (!verify(4,t,i==0?10:12,ops,z,o,d,caps[c])) return 1;
                    ++exhaustive;
                }
            }
    for (int inputs=3;inputs<=4;++inputs) {
        int n=1<<inputs;
        unsigned full=(1u<<n)-1;
        ff_width_tables(n);
        for (int j=0;j<100000;++j) {
            unsigned pi=draw()%inputs, h=0;
            for (int r=1;r<n;++r) h |= ((r>>pi)&1u)<<r;
            unsigned known=draw()&full, ones=draw()&known&~1u, z=(known&~ones)|1u;
            unsigned target=draw()&full&~1u, ops=draw()&31;
            unsigned domain=draw()&((1u<<(n/2+1))-2);
            int cap=(int)(draw()%262)-2;
            if (!verify(n,target,h,ops,z,ones,domain,cap)) return 1;
            ++sampled;
        }
    }
    printf("{\"two_input_cases\":%llu,\"three_four_input_cases\":%llu,\"seed\":17319,\"mismatches\":0}\n",
           exhaustive,sampled);
    return 0;
}
