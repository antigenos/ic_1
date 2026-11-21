/* A target-preserving shear interchanges a consumed input with a paid XOR
 * signal. The second gate is kept fixed, including its outstanding-use status. */
typedef struct {
    unsigned char high1, low1, low2, op2, high3, low3, op3;
} PrefixExclusion;

static unsigned prefix_function(unsigned high, unsigned low, int code)
{
    switch (code) {
    case 2: return high & ~low;
    case 4: return low & ~high;
    case 6: return high ^ low;
    case 8: return high & low;
    default: return high | low;
    }
}

static int prefix_prepare(unsigned target, PrefixExclusion *out)
{
    const int codes[] = {2,4,6,8,14};
    unsigned columns[] = {0xaaaa,0xcccc,0xf0f0,0xff00,0,0};
    OrbitGate first[30];
    orbit_prepare(first,target,1);
    int count = 0;
    for (int f = 0; f < 30; ++f) {
        if (!first[f].keep || first[f].code != 6) continue;
        int hi = first[f].high, lo = first[f].low;
        columns[4] = first[f].truth;
        unsigned rows[4][16];
        int n_maps = 0;
        for (int direction = 0; direction < 2; ++direction) {
            int i = direction ? hi : lo, j = direction ? lo : hi;
            for (int phase = 0; phase < 2; ++phase) {
                for (unsigned r = 0; r < 16; ++r)
                    rows[n_maps][r] = r ^ ((((r >> j) & 1u) ^ phase) << i);
                if (orbit_image(target,rows[n_maps]) == target) ++n_maps;
            }
        }
        if (!n_maps) continue;
        for (int z = 0; z < 4; ++z) for (int k = 0; k < 5; ++k) {
            unsigned g = prefix_function(columns[4],columns[z],codes[k]);
            int duplicate = !g;
            for (int a = 0; a < 5; ++a) duplicate |= columns[a] == g;
            if (duplicate) continue;
            columns[5] = g;
            int eligible[4], n = 0;
            for (int m = 0; m < n_maps; ++m)
                if (orbit_image(g,rows[m]) == g) eligible[n++] = m;
            if (!n) continue;
            for (int a = 1; a < 6; ++a) for (int b = 0; b < a; ++b) for (int c = 0; c < 5; ++c) {
                unsigned third = prefix_function(columns[a],columns[b],codes[c]);
                for (int m = 0; m < n; ++m)
                    if (orbit_image(third,rows[eligible[m]]) < third) {
                        out[count++] = (PrefixExclusion){hi,lo,z,codes[k],a,b,codes[c]};
                        break;
                    }
            }
        }
    }
    return count;
}

static void prefix_gate_clause(PexaMan_t *p, int gate, int high, int low, int code, int *lits)
{
    lits[0] = Abc_Var2Lit(p->VarMarks[gate][0][high],1);
    lits[1] = Abc_Var2Lit(p->VarMarks[gate][1][low],1);
    for (int bit = 1; bit <= 3; ++bit)
        lits[bit+1] = Abc_Var2Lit(3*(gate-4)+bit,(code >> bit) & 1);
}

static int prefix_filter(PexaMan_t *p)
{
    static int prev = -1, size = 0;
    static PrefixExclusion exclusions[6*4*5*15*5];
    if (p->nVars != 4 || p->nNodes < 3 || getenv("PEXACT_PREFIX_OFF")) return 1;
    unsigned target = (unsigned)p->pTruth[0] & 65535u;
    target = (target & 1u) ? target ^ 65535u : target;
    if ((int)target != prev) {
        size = prefix_prepare(target,exclusions);
        prev = target;
    }
    for (int i = 0; i < size; ++i) {
        PrefixExclusion x = exclusions[i];
        int lits[15];
        prefix_gate_clause(p,4,x.high1,x.low1,6,lits);
        prefix_gate_clause(p,5,4,x.low2,x.op2,lits+5);
        prefix_gate_clause(p,6,x.high3,x.low3,x.op3,lits+10);
        if (getenv("PEXACT_PREFIX_TRACE")) {
            printf("PREFIX n=%d",p->nNodes);
            for (int j = 0; j < 15; ++j) printf(" %d",lits[j]);
            printf("\n");
        }
        if (!sat_solver_addclause(p->pSat,lits,lits+15)) return 0;
    }
    return 1;
}
