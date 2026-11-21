/* The mode-2 caller owns the ledger for one normalized target/library. The
 * largest query has fewer than MAJ_NOBJS charged gates, each costs <= 128.
 * All scores are even. Bit 0 denotes arithmetical support, bit 1 proven UNSAT. */
#define WINDOW_BINS (1 + MAJ_NOBJS * 64)
typedef struct {
    unsigned char table[MAJ_NOBJS][WINDOW_BINS];
    int prepared, mode, inputs, trace;
} WindowProof;

static void window_init(WindowProof *w, int inputs)
{
    memset(w, 0, sizeof(*w));
    w->inputs = inputs;
    w->table[0][0] = 1;
    const char *mode = getenv("OPTWIN_MODE");
    w->mode = !mode || !strcmp(mode, "both") ? 3 :
              !strcmp(mode, "domain") ? 1 : !strcmp(mode, "history") ? 2 : 0;
    w->trace = getenv("OPTWIN_TRACE") != NULL;
}

static void window_prepare(WindowProof *w, int r)
{
    int rows = 1 << w->inputs, most = rows * rows / 4;
    while (w->prepared < r) {
        int level = ++w->prepared;
        int unused = w->inputs - level - 1;
        int stride = unused > 0 ? 1 << unused : 1;
        for (int a = stride; a <= rows / 2; a += stride) {
            int cost = a * (rows - a);
            for (int i = 0; i <= (level - 1) * most; ++i)
                if (w->table[level-1][i] & 1)
                    w->table[level][i+cost] |= 1;
        }
    }
}

static int window_skip(WindowProof *w, int r, int lo, int hi)
{
    if (!w->mode || r <= 0 || r >= MAJ_NOBJS || lo < 0 || hi < lo || hi/2 >= WINDOW_BINS)
        return 0;
    if (w->mode & 1) window_prepare(w, r);
    for (int s = (lo+1)/2; s <= hi/2; ++s) {
        unsigned flags = w->table[r][s];
        if ((w->mode & 1) && !(flags & 1)) continue;
        if ((w->mode & 2) && (flags & 2)) continue;
        return 0;
    }
    return 1;
}

static void window_unsat(WindowProof *w, int r, int lo, int hi)
{
    if (!(w->mode & 2) || r <= 0 || r >= MAJ_NOBJS || lo < 0 || hi < lo || hi/2 >= WINDOW_BINS)
        return;
    for (int s = (lo+1)/2; s <= hi/2; ++s)
        w->table[r][s] |= 2;
}
