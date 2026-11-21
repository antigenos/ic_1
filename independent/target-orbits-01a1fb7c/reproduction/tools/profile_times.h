#include <stdio.h>
#include <time.h>

enum phase { QUEUE_COUNTS, ENCODE, HISTOGRAM, BDD_TERMS, SOLVE, PHASE_COUNT };
static double phase_seconds[PHASE_COUNT];
static unsigned long long phase_calls[PHASE_COUNT], histogram_vectors;

/* GNU C diagnostic build only. Evaluate the original expression exactly once. */
#define MEASURE(phase_id, expression) ({                  \
    clock_t phase_start = clock();                       \
    __auto_type phase_value = (expression);              \
    phase_seconds[phase_id] +=                           \
        (double)(clock() - phase_start) / CLOCKS_PER_SEC; \
    ++phase_calls[phase_id];                             \
    phase_value;                                         \
})

static void report_phases(void) {
    printf("PHASE enumeration_s=%.6f bdd_terms_s=%.6f other_encode_s=%.6f "
           "sat_s=%.6f sat_calls=%llu bdd_terms=%llu histogram_vectors=%llu\n",
           phase_seconds[QUEUE_COUNTS] + phase_seconds[HISTOGRAM] - phase_seconds[BDD_TERMS],
           phase_seconds[BDD_TERMS], phase_seconds[ENCODE] - phase_seconds[HISTOGRAM],
           phase_seconds[SOLVE], phase_calls[SOLVE], phase_calls[BDD_TERMS], histogram_vectors);
}
