/* Observe the first decision-free fixed point of the original integrated propagation. */
static int probe_after_joint(sat_solver *s)
{
    int changed = replay_visit(s);
    ReplayQuery *q = &replay_query;
    PexaMan_t *p = q->p;
    if (changed || s->stats.decisions || q->target != 0xfe76 ||
        q->bound != 300 || p->nNodes != 4) return changed;
    int out = p->nObjs - 1, last = out - 1, lower = 0;
    for (int j = p->nVars; j < last; ++j) lower += replay_signal(q, j).min_cost;
    ReplaySignal g = replay_signal(q, last);
    for (int pi = 0; pi < 4; ++pi) {
        ReplaySignal pin = replay_signal(q, pi);
        unsigned z[2] = {g.zeros, pin.zeros}, o[2] = {g.ones, pin.ones};
        unsigned d[2] = {g.domain, pin.domain};
        int supported = p9_connection_feasible(16, q->target, replay_ops(p), z, o, d,
                                               q->bound - lower, 1);
        printf("ROOT primary=%d budget=%d other_min=%d selected=%d candidate=%d "
               "domain=%x zeros=%04x ones=%04x ops=%x public=%d queue_empty=%d\n",
               pi, q->bound, lower, sat_solver_get_var_value(s,p->VarMarks[out][0][last]),
               sat_solver_get_var_value(s,p->VarMarks[out][1][pi]), g.domain, g.zeros, g.ones,
               replay_ops(p), supported, s->qhead == s->qtail);
    }
    return changed;
}
