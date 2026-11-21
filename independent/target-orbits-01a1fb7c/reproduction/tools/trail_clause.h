/* Installed only in the independently built serial research SAT solver. */
int (*replay_at_fixpoint)(sat_solver *) = NULL;

int replay_imply(sat_solver *s, int *clause, int size)
{
    int watch = 1;
    assert(size >= 2 && var_value(s, lit_var(clause[0])) == varX);
    for (int i = 1; i < size; ++i) {
        int v = lit_var(clause[i]);
        assert(var_value(s, v) != varX && var_value(s, v) != lit_sign(clause[i]));
        if (var_level(s, v) > var_level(s, lit_var(clause[watch]))) watch = i;
    }
    /* Keep the implied literal at the correct decision level; checking is optional. */
    if (var_level(s, lit_var(clause[watch])) != sat_solver_dl(s)) return 0;
    int tmp = clause[watch];
    clause[watch] = clause[1];
    clause[1] = tmp;
    int reason = sat_solver_clause_new(s, clause, clause + size, 1);
    check(sat_solver_enqueue(s, clause[0], reason));
    return 1;
}
