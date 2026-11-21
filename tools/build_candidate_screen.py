"""Apply each small experiment independently to the frozen joint integration."""
import argparse
import shutil
from build_variant import ROOT, build

MODES = ("memo", "xor", "schedule", "guide", "short", "plain", "prefix", "symmetry","windows")


def replace_once(code, old, new):
    if code.count(old) != 1:
        raise ValueError(f"Source anchor count {code.count(old)} for {old}")
    return code.replace(old, new)


def make(mode):
    base = (ROOT / "tools/joint_trail.h").read_text()
    source = base
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
    elif mode in ("prefix","plain","symmetry"):
        if mode=="symmetry":
            include="#define SCREEN_SYMMETRY\n"
        else:
            include=f'#define SCREEN_SHIFT {int(mode=="prefix")}\n#include "screen_prefix_table.h"\n'
        source = replace_once(source,"static int replay_solve(",include+'#include "screen_structural.h"\nstatic int replay_solve(')
        anchor='    const char *rules = getenv("REPLAY_RULES");'
        source=replace_once(source,anchor,"    if (!screen_structural(p, bound)) return l_False;\n"+anchor)
    else:
        raise ValueError(mode)
    name = "screen-" + mode
    dest = ROOT / ".local/variants" / name
    dest.mkdir(parents=True, exist_ok=True)
    if mode in ("plain","prefix"):
        shutil.copyfile(ROOT/".local/screen_prefix_table.h",dest/"screen_prefix_table.h")
    (dest / "joint_trail.h").write_text(source)
    patches = [ROOT / "variants" / (n + ".patch") for n in ("compositions","support","joint-trail")]
    if mode=="windows":
        patches.append(ROOT/"variants/screen-window-observation.patch")
    build(name, patches, ROOT / "variants/sat-trail.patch")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=MODES)
    make(p.parse_args().mode)
