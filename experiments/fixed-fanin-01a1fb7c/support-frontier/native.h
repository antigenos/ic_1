/* Fast path for the author CLI's four-input binary-search mode. */
#define FF_FIXED_TOPOLOGY_ACTIVITY 1
#include "pareto_verify.h"
#include "pareto_table.h"

static int pareto_emit(Bmc_EsPar_t *pars, word *truth, int complement)
{
    if (pars->nVars != 4 || pars->fOnlyAnd) return 0;
    unsigned t = (unsigned)(truth[0] & 65535);
    int lo = 0, hi = (int)(sizeof(pareto_entries) / sizeof(pareto_entries[0]));
    while (lo < hi) {
        int mid = lo + (hi-lo)/2;
        if (pareto_entries[mid].truth < t) lo = mid+1;
        else hi = mid;
    }
    if (lo >= (int)(sizeof(pareto_entries) / sizeof(pareto_entries[0]))
        || pareto_entries[lo].truth != t) return 0;
    Bmc_EsPar_t scratch = *pars;
    PexaMan_t *cert = NULL;
    int ok = ff_native_library(&scratch, truth, &cert, pareto_entries[lo].spec);
    if (ok) {
        puts("PARETO_CERTIFIED");
        PexaManPrintSolution(cert, complement, true);
    }
    if (cert) PexaManFree(cert);
    return ok;
}
