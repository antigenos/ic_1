/* Independent pexact integration of the pinned MIT TCJAP local evaluator. */
#include "joint_relation.h"

extern int (*replay_at_fixpoint)(sat_solver *);
extern int replay_imply(sat_solver *, int *, int);
typedef struct {
    unsigned zeros, ones, domain;
    int min_cost;
} ReplaySignal;

typedef struct {
    PexaMan_t *p;
    int rows, bound, use_budget, trace, counts_enabled, early_enabled;
    unsigned target;
    unsigned long long visits, checks, counts, edges;
} ReplayQuery;
static ReplayQuery replay_query;

static int replay_row_var(PexaMan_t *p, int obj, int row)
{
    return p->iVarMintermBase + 3 * (obj - p->nVars + 1) + (row - 1) * 3 * p->nNodes;
}

static int replay_count_var(PexaMan_t *p, int obj, int rows, int a)
{
    return p->pMap[(obj - p->nVars) * (rows / 2) + a - 1].var;
}

static ReplaySignal replay_signal(ReplayQuery *q, int obj)
{
    PexaMan_t *p = q->p;
    int n = q->rows;
    ReplaySignal v = {1, 0, 0, 0};
    if (obj < p->nVars) {
        for (int r = 1; r < n; ++r)
            if ((r >> obj) & 1) v.ones |= 1u << r;
        v.zeros = ((1u << n) - 1) ^ v.ones;
        v.domain = 1u << (n / 2);
        return v;
    }
    for (int r = 1; r < n; ++r) {
        int val = sat_solver_get_var_value(p->pSat, replay_row_var(p, obj, r));
        if (val == l_False) v.zeros |= 1u << r;
        if (val == l_True) v.ones |= 1u << r;
    }
    for (int a = 1; a <= n / 2; ++a) {
        int var = replay_count_var(p, obj, n, a);
        if (sat_solver_get_var_value(p->pSat, var) != l_False) {
            if (!v.domain) v.min_cost = 2 * a * (n - a);
            v.domain |= 1u << a;
        }
    }
    return v;
}

static unsigned replay_ops(PexaMan_t *p)
{
    const unsigned codes[5] = {2, 4, 6, 8, 14};
    unsigned mask = 31;
    int base = 1 + 3 * (p->nNodes - 1);
    for (int b = 0; b < 3; ++b) {
        int val = sat_solver_get_var_value(p->pSat, base + b);
        if (val == l_Undef) continue;
        for (int k = 0; k < 5; ++k)
            if (((codes[k] >> (b + 1)) & 1) != (val == l_True)) mask &= ~(1u << k);
    }
    return mask;
}

/* Premises are negated in the clause. All listed variable families are disjoint. */
static int replay_explain(ReplayQuery *q, const int obj[2], int unselected_pin,
                          int victim, ReplaySignal *signals)
{
    PexaMan_t *p = q->p;
    sat_solver *s = p->pSat;
    int out = p->nObjs - 1, n = q->rows;
    int clause[2 + 2 + 3 + 2 * 16 + MAJ_NOBJS * 8], size = 0;
    clause[size++] = Abc_Var2Lit(victim, 1);
    for (int k = 0; k < 2; ++k)
        if (k != unselected_pin)
            clause[size++] = Abc_Var2Lit(p->VarMarks[out][k][obj[k]], 1);
    for (int b = 0; b < 3; ++b) {
        int var = 1 + 3 * (p->nNodes - 1) + b;
        int val = sat_solver_get_var_value(s, var);
        if (val != l_Undef) clause[size++] = Abc_Var2Lit(var, val == l_True);
    }
    for (int k = 0; k < 2; ++k) {
        int j = obj[k];
        if (j < p->nVars) continue;
        for (int r = 1; r < n; ++r) {
            unsigned bit = 1u << r;
            if ((signals[j].zeros | signals[j].ones) & bit)
                clause[size++] = Abc_Var2Lit(replay_row_var(p, j, r), !!(signals[j].ones & bit));
        }
    }
    for (int j = p->nVars; j < out; ++j) {
        if (j != obj[0] && j != obj[1] && !q->use_budget) continue;
        for (int a = 1; a <= n / 2; ++a) {
            if (signals[j].domain & (1u << a)) {
                if (j != obj[0] && j != obj[1]) break;  /* lower bound established */
            } else clause[size++] = Abc_Var2Lit(replay_count_var(p, j, n, a), 0);
        }
    }
    if (!replay_imply(s, clause, size)) return 0;
    if (q->trace) {
        printf("REASON %d %d %x %d %d %d %d", p->nVars, p->nNodes, q->target,
               q->use_budget ? q->bound : 32767, obj[0], obj[1], unselected_pin);
        for (int i = 0; i < size; ++i) printf(" %d", clause[i]);
        puts("");
    }
    return 1;
}

static int replay_pair(ReplayQuery *q, ReplaySignal *signals, int total_min, unsigned ops,
                       const int obj[2], int unselected_pin)
{
    PexaMan_t *p = q->p;
    const ReplaySignal x = signals[obj[0]], y = signals[obj[1]];
    unsigned zeros[2] = {x.zeros, y.zeros}, ones[2] = {x.ones, y.ones};
    unsigned domains[2] = {x.domain, y.domain};
    unsigned charged = (obj[0] >= p->nVars) + 2 * (obj[1] >= p->nVars);
    int cap = q->use_budget ? q->bound - (total_min - x.min_cost - y.min_cost) : 32767;
    P9JointResult result;
    ++q->checks;
    if (p9_joint_support(q->rows, q->target, ops, zeros, ones, domains, cap, charged, &result))
        abort();
    if (unselected_pin >= 0) {
        if (result.supported[0]) return 0;
        int selector = p->VarMarks[p->nObjs - 1][unselected_pin][obj[unselected_pin]];
        if (!replay_explain(q, obj, unselected_pin, selector, signals)) return 0;
        ++q->edges;
        return 1;
    }
    for (int k = 0; k < 2; ++k) {
        if (!(charged & (1u << k))) continue;
        unsigned missing = domains[k] & ~result.supported[k];
        for (int a = 1; a <= q->rows / 2; ++a) if (missing & (1u << a)) {
            int var = replay_count_var(p, obj[k], q->rows, a);
            if (sat_solver_get_var_value(p->pSat, var) == l_Undef &&
                replay_explain(q, obj, unselected_pin, var, signals)) {
                ++q->counts;
                return 1;
            }
        }
    }
    return 0;
}

static int replay_visit(sat_solver *s)
{
    ReplayQuery *q = &replay_query;
    PexaMan_t *p = q->p;
    int out = p->nObjs - 1, obj[2] = {-1, -1};
    ++q->visits;
    for (int k = 0; k < 2; ++k)
        for (int j = 0; j < out - k; ++j)
            if (sat_solver_get_var_value(s, p->VarMarks[out][k][j]) == l_True) {
                obj[k] = j;
                break;
            }
    if (obj[0] < 0 && obj[1] < 0) return 0;
    int open = obj[0] < 0 ? 0 : (obj[1] < 0 ? 1 : -1);
    if (open < 0 ? !q->counts_enabled : !q->early_enabled) return 0;
    ReplaySignal signals[MAJ_NOBJS];
    int total_min = 0;
    for (int j = 0; j < out; ++j) {
        signals[j] = replay_signal(q, j);
        if (!signals[j].domain) return 0;
        total_min += signals[j].min_cost;
    }
    unsigned ops = replay_ops(p);
    if (open < 0) return replay_pair(q, signals, total_min, ops, obj, -1);
    for (int j = 0; j < out - open; ++j) {
        obj[open] = j;
        if (obj[0] <= obj[1]) continue;
        int var = p->VarMarks[out][open][j];
        if (sat_solver_get_var_value(s, var) != l_Undef) continue;
        if (replay_pair(q, signals, total_min, ops, obj, open)) return 1;
    }
    return 0;
}

static int replay_solve(PexaMan_t *p, int bound)
{
    const char *rules = getenv("REPLAY_RULES");
    if (rules && !strcmp(rules, "off"))
        return sat_solver_solve(p->pSat, NULL, NULL, 0, 0, 0, 0);
    if (!rules) rules = "both";
    ReplayQuery *q = &replay_query;
    memset(q, 0, sizeof(*q));
    q->counts_enabled = !strcmp(rules, "counts") || !strcmp(rules, "both");
    q->early_enabled = !strcmp(rules, "early") || !strcmp(rules, "both");
    if (!q->counts_enabled && !q->early_enabled) abort();
    q->p = p;
    q->rows = 1 << p->nVars;
    q->target = (unsigned)p->pTruth[0] & ((1u << q->rows) - 1);
    q->bound = bound;
    const char *budget = getenv("REPLAY_BUDGET");
    q->use_budget = !budget || strcmp(budget, "0");
    q->trace = getenv("REPLAY_TRACE") != NULL;
    replay_at_fixpoint = replay_visit;
    int result = sat_solver_solve(p->pSat, NULL, NULL, 0, 0, 0, 0);
    replay_at_fixpoint = NULL;
    if (q->trace || getenv("REPLAY_STATS"))
        printf("JOINT gates=%d bound=%d visits=%llu checks=%llu counts=%llu edges=%llu conflicts=%d\n",
               p->nNodes, bound, q->visits, q->checks, q->counts, q->edges,
               sat_solver_nconflicts(p->pSat));
    return result;
}
