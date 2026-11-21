"""Apply each small experiment independently to the frozen joint integration."""
import argparse
import shutil
from build_variant import ROOT, build

MODES = ("memo", "xor", "schedule", "guide", "short", "plain", "prefix", "symmetry","windows",
         "interval","holes","exists","combined","ordered")


def replace_once(code, old, new):
    if code.count(old) != 1:
        raise ValueError(f"Source anchor count {code.count(old)} for {old}")
    return code.replace(old, new)


def make(mode):
    base = (ROOT / "tools/joint_trail.h").read_text()
    source = base
    name = "screen-" + mode
    dest = ROOT / ".local/variants" / name
    dest.mkdir(parents=True, exist_ok=True)
    if mode in ("memo", "xor"):
        include = '#include "screen_support.h"\n'
        if mode == "memo":
            include = "#define SCREEN_MEMO\n" + include
        source = replace_once(source, "static int replay_pair(", include + "static int replay_pair(")
        source = replace_once(source, "if (p9_joint_support(", "if (screen_support(")
    elif mode == "schedule":
        anchor = "    ReplaySignal signals[MAJ_NOBJS];"
        guard = """    if (open < 0) {
        int pending = 0;
        for (int k = 0; k < 2 && !pending; ++k) {
            if (obj[k] < p->nVars) continue;
            for (int a = 1; a <= q->rows / 2; ++a) {
                int v = replay_count_var(p, obj[k], q->rows, a);
                if (sat_solver_get_var_value(s, v) == l_Undef) { pending = 1; break; }
            }
        }
        if (!pending) return 0;
    }
"""
        source = replace_once(source, anchor, guard + anchor)
    elif mode == "guide":
        anchor = "    replay_at_fixpoint = replay_visit;"
        guide = """    int advice[3 + 2*MAJ_NOBJS], used = 0, out = p->nObjs - 1;
    for (int i = 0; i < 3; ++i) advice[used++] = 1 + 3*(p->nNodes - 1) + i;
    for (int pin = 0; pin < 2; ++pin)
        for (int j = 0; j < out-pin; ++j) advice[used++] = p->VarMarks[out][pin][j];
    sat_solver_set_var_activity(p->pSat, advice, used);
"""
        source = replace_once(source, anchor, guide + anchor)
    elif mode == "short":
        source = replace_once(source, "int victim, ReplaySignal *signals)",
                              "int victim, ReplaySignal *signals, int budget_needed)")
        source = replace_once(source, "&& !q->use_budget) continue;",
                              "&& (!q->use_budget || !budget_needed)) continue;")
        source = replace_once(source, "selector, signals))",
                              "selector, signals, result.without_budget[0] != 0))")
        source = replace_once(source, "var, signals))",
                              "var, signals, (result.without_budget[k] >> a) & 1u))")
    elif mode in ("interval","holes"):
        source=replace_once(source,"static int replay_pair(",
            f'#define SCREEN_HOLES {int(mode=="holes")}\n#include "screen_window_filter.h"\nstatic int replay_pair(')
        source=replace_once(source,"    if (unselected_pin >= 0) {",
            "    screen_refine(q,signals,obj,unselected_pin,ops,zeros,ones,domains,cap,charged,&result);\n    if (unselected_pin >= 0) {")
        source=replace_once(source,"if (j != obj[0] && j != obj[1]) break;","/* Every excluded cost in an unrelated gate can affect the finite sumset. */")
        anchor='    q->trace = getenv("REPLAY_TRACE") != NULL;'
        source=replace_once(source,anchor,anchor+'\n    if (q->trace) printf("WINDOW_BOUND %d %d\\n",screen_lower,bound);')
    elif mode == "exists":
        pinned=(ROOT/".local/reference/src/joint_relation.c").read_text()
        kernel=pinned.split("int p9_joint_support(",1)[0]
        kernel=replace_once(kernel,"static void P9ClosedSupport(","static int ScreenExists(")
        kernel=replace_once(kernel,"if(bs){support[0]|=1u<<minority;support[1]|=bs;}","if(bs) return 1;")
        kernel=replace_once(kernel,"if(bs){plain[0]|=1u<<minority;plain[1]|=bs;}","")
        kernel=kernel.rstrip()
        assert kernel.endswith("}")
        (dest/"screen_exists_core.h").write_text(kernel[:-1]+" return 0;\n}\n")
        source=replace_once(source,"static int replay_pair(",'#include "screen_exists_core.h"\nstatic int replay_pair(')
        source=replace_once(source,"    if (p9_joint_support(q->rows",
            """    if (unselected_pin>=0) {
        if (ScreenExists(q->rows,q->target,ops,zeros,ones,domains,NULL,NULL,cap,charged&1,(charged>>1)&1)) return 0;
        result.supported[0]=0;
    } else if (p9_joint_support(q->rows""")
    elif mode == "windows":
        source=replace_once(source,"static int replay_pair(",'#include "sample_joint_windows.h"\nstatic int replay_pair(')
        source=replace_once(source,"    if (unselected_pin >= 0) {","    screen_observe(q,signals,obj,unselected_pin,ops,&result);\n    if (unselected_pin >= 0) {")
        wrapper="""static int screen_visit(sat_solver *s)
{
    screen_sample[0]=0;
    int changed=replay_visit(s);
    if (!changed && screen_sample[0]) { puts(screen_sample); ++screen_sampled; }
    return changed;
}
"""
        source=replace_once(source,"static int replay_solve(",wrapper+"\nstatic int replay_solve(")
        source=replace_once(source,"    replay_at_fixpoint = replay_visit;","    screen_sampled=0;\n    replay_at_fixpoint = screen_visit;")
    elif mode=="ordered":
        source=replace_once(source,"static int replay_solve(",'#include "screen_ordered_inputs.h"\nstatic int replay_solve(')
        anchor='    const char *rules = getenv("REPLAY_RULES");'
        source=replace_once(source,anchor,"    if (!screen_input_order(p)) return l_False;\n"+anchor)
    elif mode in ("prefix","plain","symmetry","combined"):
        if mode=="symmetry":
            include="#define SCREEN_SYMMETRY\n"
        else:
            include=f'#define SCREEN_SHIFT {int(mode!="plain")}\n#include "screen_prefix_table.h"\n'
        if mode=="combined":
            include+=('#define screen_structural screen_prefix_only\n#include "screen_structural.h"\n'
                      '#undef screen_structural\n#define SCREEN_SYMMETRY\n')
        source = replace_once(source,"static int replay_solve(",include+'#include "screen_structural.h"\nstatic int replay_solve(')
        anchor='    const char *rules = getenv("REPLAY_RULES");'
        filters="    if (!screen_structural(p, bound)) return l_False;\n"
        if mode=="combined":
            filters+="    if (!screen_prefix_only(p, bound)) return l_False;\n"
        source=replace_once(source,anchor,filters+anchor)
    else:
        raise ValueError(mode)
    if mode in ("plain","prefix","combined"):
        shutil.copyfile(ROOT/".local/screen_prefix_table.h",dest/"screen_prefix_table.h")
    (dest / "joint_trail.h").write_text(source)
    patches = [ROOT / "variants" / (n + ".patch") for n in ("compositions","support","joint-trail")]
    if mode in ("windows","interval","holes"):
        patches.append(ROOT/"variants/screen-window-observation.patch")
    build(name, patches, ROOT / "variants/sat-trail.patch")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=MODES)
    make(p.parse_args().mode)
