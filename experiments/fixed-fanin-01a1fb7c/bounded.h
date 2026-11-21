/* A complete cold search up to a finite activity budget; overflow yields UNKNOWN. */
#include <stdlib.h>
#include <string.h>
#include "prefix.h"

enum { FF_PAID_LIMIT = 12, FF_BUDGET = 360, FF_WORK = 2000000 };
typedef struct { unsigned char hi, lo, op; } FfGate;
typedef struct {
    int complete, found, cost, gates;
    unsigned visited, pruned;
    FfGate chain[FF_PAID_LIMIT + 1];
} FfCertificate;
typedef struct {
    unsigned signals[4 + FF_PAID_LIMIT];
    FfGate chain[FF_PAID_LIMIT + 1];
    unsigned (*marks)[32768];
    FfPrefix relaxation;
    int use_relaxation;
    int ceiling;
    unsigned work;
    FfCertificate result;
} FfSearch;

static unsigned ff_gate(unsigned a, unsigned b, int k)
{
    switch (k) {
    case 0: return a & ~b;
    case 1: return b & ~a;
    case 2: return a ^ b;
    case 3: return a & b;
    default: return a | b;
    }
}

static void ff_visit(FfSearch *s, int depth, int paid, int inherited)
{
    static const unsigned char codes[] = {2, 4, 6, 8, 14};
    FfCertificate *r = &s->result;
    if (!r->complete || paid >= r->cost) return;
    if (r->visited == s->work) {
        r->complete = 0;
        return;
    }
    unsigned id = ++r->visited;
    int size = 4 + depth;
    /* A free output using only older wires was checked in its ancestor. */
    for (int i = depth ? size - 1 : 1; i < size; ++i) {
        for (int j = 0; j < i; ++j) {
            for (int k = 0; k < 5; ++k) {
                if (ff_gate(s->signals[i], s->signals[j], k) != s->relaxation.target) continue;
                s->chain[depth] = (FfGate){i, j, codes[k]};
                r->gates = depth + 1;
                memcpy(r->chain, s->chain, r->gates * sizeof(FfGate));
                r->found = 1;
                r->cost = paid;
                return;
            }
        }
    }
    if (paid + 30 >= r->cost || depth >= FF_PAID_LIMIT) return;
    if (s->use_relaxation && depth <= 2) {
        FfPrefix *p = &s->relaxation;
        p->depth_limit = depth;
        for (int i = 0; i < depth; ++i) p->wires[4+i] = s->signals[4+i];
        inherited = ff_prefix_lower(p, depth, paid, inherited);
    }
    if (inherited >= r->cost) {
        ++r->pruned;
        return;
    }
    for (int i = 1; i < size && r->complete; ++i) {
        /* In a lexicographically minimal topological ordering, a gate ready
           after signal i cannot be emitted after a larger independent gate. */
        unsigned ordered_after = 0;
        for (int m = i + 1 < 4 ? 4 : i + 1; m < size; ++m)
            if (s->signals[m] > ordered_after) ordered_after = s->signals[m];
        for (int j = 0; j < i; ++j) {
            for (int k = 0; k < 5; ++k) {
                unsigned g = ff_gate(s->signals[i], s->signals[j], k);
                if (!g || g < ordered_after || s->marks[depth][g >> 1] == id) continue;
                int next = paid + ff_activity(g, 16);
                if (next >= r->cost) continue;
                int m = 0;
                while (m < size && s->signals[m] != g) ++m;
                if (m < size) continue;
                s->marks[depth][g >> 1] = id;
                s->signals[size] = g;
                s->chain[depth] = (FfGate){i, j, codes[k]};
                ff_visit(s, depth + 1, next, inherited);
            }
        }
    }
}

static FfCertificate ff_bounded(unsigned target, int ceiling, unsigned work, int projected)
{
    FfSearch s = {0};
    s.ceiling = ceiling;
    s.work = work;
    s.use_relaxation = projected;
    s.relaxation.target = target;
    s.result.cost = ceiling + 1;
    if (ceiling < 0 || ceiling > FF_BUDGET || (target & 1u)) return s.result;
    for (int i = 0; i < 4; ++i) s.signals[i] = ff_primary(16, i);
    s.marks = calloc(FF_PAID_LIMIT, sizeof(*s.marks));
    if (!s.marks) return s.result;
    FfRestrictions cuts;
    if (projected) {
        ff_init_restrictions(&cuts);
        s.relaxation.cuts = &cuts;
        for (int cut = 0; cut < 10; ++cut)
            for (int side = 0; side < 2; ++side)
                s.relaxation.target_slices[cut][side] = ff_slice(&cuts, target, cut, side);
    }
    s.result.complete = 1;
    ff_visit(&s, 0, 0, 0);
    free(s.marks);
    return s.result;
}
