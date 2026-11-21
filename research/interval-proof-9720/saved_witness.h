/* Complete a strict lower-bound proof without discarding the model that supplies
 * the upper bound. Failure to construct any residual query leaves the original
 * model and original search available. */
static int window_support(const PexaMan_t *p)
{
    int rows = 1 << p->nVars, total = 0;
    unsigned truth = (unsigned)p->pTruth[0];
    for (int v = 0; v < p->nVars; ++v)
        for (int i = 0; i < rows; ++i)
            if (((truth >> i) ^ (truth >> (i ^ (1 << v)))) & 1u) {
                ++total;
                break;
            }
    return total;
}

static int window_certify(WindowProof *w, PexaMan_t **original)
{
    PexaMan_t *first = *original, *best = first;
    Bmc_EsPar_t *params = first->pPars;
    int support = window_support(first), rows = 1 << first->nVars;
    int upper = PexaManGetAct(first), saved_nodes = params->nNodes;
    if (support < 3 || w->mode != 3 || upper <= 0 || upper/2 >= WINDOW_BINS) return 0;
    if (w->trace) printf("INCUMBENT score=%d support=%d\n", upper, support);
    /* A connected binary circuit with r paid gates and one output gate has
     * at most r+2 different input leaves. Every paid gate is nonconstant. */
    for (int r = support - 2; r < MAJ_NOBJS - first->nVars && r * 2 * (rows - 1) < upper; ++r) {
        window_prepare(w, r);
        for (;;) {
            int lo = -1, hi = -1;
            for (int s = 0; 2*s < upper; ++s)
                if (w->table[r][s] == 1) {
                    if (lo < 0) lo = 2*s;
                    hi = 2*s;
                }
            if (lo < 0) break;
            params->nNodes = r + 1;
            PexaMan_t *q = PexaManAlloc(params, first->pTruth);
            if (!q) goto unfinished;
            Comb_t node = {0};
            node.act = lo;
            node.r = r;
            if (!ExactPowerSynthesisCnfBddRange(params, q, &node, hi-lo)) {
                if (w->trace) printf("UNFINISHED r=%d lo=%d hi=%d\n", r,lo,hi);
                PexaManFree(q);
                goto unfinished;
            }
            int status = replay_solve(q, hi);
            int score = status == l_True ? PexaManGetAct(q) : -1;
            if (w->trace) printf("STRICT r=%d lo=%d hi=%d status=%d score=%d\n", r,lo,hi,status,score);
            if (status == l_False) {
                window_unsat(w,r,lo,hi);
                PexaManFree(q);
                break;
            }
            if (status != l_True || score < lo || score > hi || score >= upper) {
                PexaManFree(q);
                goto unfinished;
            }
            if (best != first) PexaManFree(best);
            best = q;
            upper = score;
        }
    }
    if (w->trace) printf("CERTIFIED score=%d\n", upper);
    if (best != first) PexaManFree(first);
    params->nNodes = best->nNodes;
    *original = best;
    return 1;

unfinished:
    if (best != first) PexaManFree(best);
    params->nNodes = saved_nodes;
    return 0;
}
