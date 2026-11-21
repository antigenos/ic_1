/* Inject one stated hypothesis into a disposable copy of one real query. */
static int ff_diagnostic_active;
static void ff_diagnostic_setup(ReplayQuery *q)
{
    PexaMan_t *p = q->p;
    ff_diagnostic_active = q->target == 0xfe76 && q->bound == 300 && p->nNodes == 4;
    if (!ff_diagnostic_active) return;
    const char *arg = getenv("FF_PRIMARY");
    int pi = arg ? atoi(arg) : -1;
    if (pi < 0 || pi >= p->nVars) exit(4);
    lit take = Abc_Var2Lit(p->VarMarks[p->nObjs - 1][1][pi], 0);
    if (!sat_solver_addclause(p->pSat, &take, &take + 1)) {
        printf("FF_ROOT pi=%d conflict=1\n", pi);
        exit(0);
    }
}

static int ff_diagnostic_visit(sat_solver *s)
{
    int changed = replay_visit(s);
    if (!ff_diagnostic_active || changed) return changed;
    ReplayQuery *q = &replay_query;
    PexaMan_t *p = q->p;
    int pi = atoi(getenv("FF_PRIMARY"));
    ReplaySignal g = replay_signal(q, p->nObjs - 2);
    printf("FF_ROOT pi=%d conflict=0 decisions=%llu queue=%d chosen=%d high=%d "
           "zeros=%x ones=%x domain=%x ops=%x\n", pi, (unsigned long long)s->stats.decisions,
           s->qhead == s->qtail, sat_solver_get_var_value(s,p->VarMarks[p->nObjs-1][1][pi]),
           sat_solver_get_var_value(s,p->VarMarks[p->nObjs-1][0][p->nObjs-2]), g.zeros,
           g.ones, g.domain, replay_ops(p));
    exit(0);
}
