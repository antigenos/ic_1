static int ff_only_xor(unsigned target,int inputs)
{
    int rows=1<<inputs;
    unsigned full=(1u<<rows)-1;
    for (int pi=0;pi<inputs;++pi) {
        unsigned h=0;
        for (int r=0;r<rows;++r) h|=((r>>pi)&1u)<<r;
        if (!(target&h) || !(target&(full^h)) || !((full^target)&h) ||
            !((full^target)&(full^h))) return 0;
    }
    return 1;
}
