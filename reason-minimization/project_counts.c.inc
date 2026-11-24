/* Append the same prefix as joint. Save the original tail for the level fallback. */
    int original[sizeof(clause)/sizeof(clause[0])];
    int original_size = size;
    memcpy(original, clause, sizeof(int)*size);
    for (int j = p->nVars; j < out; ++j) {
        int endpoint = j == obj[0] || j == obj[1];
        if (!endpoint && !q->use_budget) continue;
        int lo = endpoint ? __builtin_popcount(signals[j].ones) : 0;
        int hi = endpoint ? n - __builtin_popcount(signals[j].zeros) : n;
        for (int a = 1; a <= n/2; ++a) {
            if (signals[j].domain & (1u << a)) {
                if (!endpoint) break;
                continue;
            }
            int lit = Abc_Var2Lit(replay_count_var(p, j, n, a), 0);
            original[original_size++] = lit;
            if (endpoint && (j == victim_obj ||
                ((a < lo || a > hi) && (n-a < lo || n-a > hi)))) continue;
            clause[size++] = lit;
        }
    }
    int accepted = replay_imply(s, clause, size);
    int fallback = !accepted && size != original_size;
    if (fallback) {
        size = original_size;
        memcpy(clause, original, size*sizeof(int));
        accepted = replay_imply(s, clause, size);
    }
#ifdef RM_DIAG
    rm_finish_attempt(unselected_pin >= 0, started, fallback);
    if (q->trace && accepted) {
        printf("ORIGINAL");
        for (int i=0; i<original_size; ++i) printf(" %d",original[i]);
        puts("");
    }
#endif
    if (!accepted) return 0;
