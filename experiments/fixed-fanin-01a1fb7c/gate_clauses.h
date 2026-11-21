/* Literals are ABC integers: 2*variable + sign, sign 1 means negated. */
typedef int (*FfAddClause)(void *, int *, int);
static const unsigned ff_codes[5] = {2,4,6,8,14};

static int ff_define_types(void *context, FfAddClause add, const int types[5], int bit_base)
{
    int choose[5];
    for (int k=0; k<5; ++k) {
        choose[k] = 2*types[k];
        for (int b=0; b<3; ++b) {
            int value = (ff_codes[k] >> (b+1)) & 1u;
            int clause[2] = {2*types[k]+1, 2*(bit_base+b)+!value};
            if (!add(context,clause,2)) return 0;
        }
    }
    return add(context,choose,5);
}

static int ff_type_row(void *context, FfAddClause add, const int types[5],
                       int high, int low, int target)
{
    for (int k=0; k<5; ++k) {
        unsigned mask = target ? ff_codes[k] : 15u ^ ff_codes[k];
        int guard = 2*types[k]+1;
        if (!(mask & (mask-1))) {
            unsigned pair = __builtin_ctz(mask);
            int a[] = {guard,2*high+!(pair & 1)};
            int b[] = {guard,2*low+!(pair & 2)};
            if (!add(context,a,2) || !add(context,b,2)) return 0;
        } else {
            for (unsigned pair=0; pair<4; ++pair) if (!(mask & (1u<<pair))) {
                int clause[] = {guard,2*high+(int)(pair & 1),2*low+(int)(pair >> 1)};
                if (!add(context,clause,3)) return 0;
            }
        }
    }
    return 1;
}
