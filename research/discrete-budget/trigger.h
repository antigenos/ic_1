/* A witness using the minimum cost of every other gate suffices for all
       surviving pairs if the two marginal minima already cross the lower end. */
#ifdef DB_PROFILE
    ++trigger_considered;
    long long start_trigger = stamp();
#endif
    int smallest = q->bound - cap;
    for (int pin = 0; pin < 2; ++pin) {
        if (charged & (1u << pin)) {
            int a = __builtin_ctz(result->supported[pin]);
            smallest += 2 * a * (q->rows - a);
        }
    }
#ifdef DB_PROFILE
    trigger_ticks += stamp() - start_trigger;
#endif
    if (smallest >= screen_lower) return;
    const int use_holes = 1;
