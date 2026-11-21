#include <stdio.h>
#include "histograms.h"

static bool emit(const int *bins, void *data)
{
    int gates=*(int *)data;
    unsigned long long original_index=0;
    for (int b=7;b>=0;--b) original_index=original_index*(gates+1)+bins[b];
    printf(" %llu",original_index);
    return true;
}

int main(void)
{
    int gates,score,counts[8]={0},weights[8];
    for (int i=0;i<8;++i) weights[i]=2*(i+1)*(15-i);
    while (scanf("%d %d",&gates,&score)==2) {
        if (gates<0 || gates>24 || score<0) return 2;
        printf("%d %d",gates,score);
        visit_histograms(7,gates,0,score,score,weights,counts,emit,&gates);
        putchar('\n');
    }
    return 0;
}
