"""Compile this experiment in a private build directory with the frozen host."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_variant import build


def compile_variant(kind):
    name = "fixed-fanin-" + kind
    dest = ROOT / ".local/variants" / name
    dest.mkdir(parents=True, exist_ok=True)
    header = (ROOT / "tools/joint_trail.h").read_text()
    if kind != "base":
        hook = "static int replay_solve(PexaMan_t *p, int bound)"
        marker = "    replay_at_fixpoint = replay_visit;"
        assert header.count(hook) == header.count(marker) == 1
        header = header.replace(hook, (HERE / (kind + ".h")).read_text() + "\n" + hook)
        if kind == "diagnostic":
            replacement = "    ff_diagnostic_setup(q);\n    replay_at_fixpoint = ff_diagnostic_visit;"
        else:
            replacement = "    if (!ff_add_clauses(q)) return l_False;\n" + marker
        header = header.replace(marker, replacement)
    (dest / "joint_trail.h").write_text(header)
    patches = []
    for tag in ("compositions", "support", "joint-trail", "sat-trail"):
        path = dest / (tag + ".patch")
        # The pinned source archives use LF even in a Windows autocrlf checkout.
        path.write_bytes((ROOT / "variants" / path.name).read_bytes().replace(b"\r\n", b"\n"))
        patches.append(path)
    build(name, patches[:-1], patches[-1])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=("base", "diagnostic", "candidate"))
    compile_variant(p.parse_args().kind)
