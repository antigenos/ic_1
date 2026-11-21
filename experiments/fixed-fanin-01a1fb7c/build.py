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
    if kind in ("library-check","library-check-fast","library-check-fixed"):
        source=(HERE/"native_library.h").read_bytes()
        if kind=="library-check-fixed":
            source=b"#define FF_FIXED_TOPOLOGY_ACTIVITY 1\n"+source
        (dest/"native_library.h").write_bytes(source)
        patch = dest/"native_library.patch"
        patch.write_bytes((HERE/"native_library.patch").read_bytes().replace(b"\r\n", b"\n"))
        patches=[patch]
        if kind=="library-check-fast":
            enumeration=dest/"compositions.patch"
            enumeration.write_bytes((ROOT/"variants/compositions.patch").read_bytes().replace(b"\r\n",b"\n"))
            patches.insert(0,enumeration)
        build(name, patches)
        return
    header = (ROOT / "tools/joint_trail.h").read_text()
    search_hooks = {"partition": ("partition.h", "ff_partition"),
                    "xor-proof": ("xor_proof.h", "ff_xor_search"),
                    "cofactor": ("cofactor_hook.h", "ff_cofactor_search")}
    initial_hooks = {"prefix": ("seed_hook.h", "seed.patch"), "bounded": ("bounded_hook.h", "bounded.patch"),
                     "tail": ("bounded_hook.h", "bounded.patch")}
    if kind in initial_hooks:
        initial_header, _ = initial_hooks[kind]
        for file in (initial_header, "cofactor.h", "prefix.h"):
            (dest / file).write_bytes((HERE / file).read_bytes())
        if kind in ("bounded", "tail"):
            for file in ("bounded.h", "tail.h", "projection.h"):
                (dest / file).write_bytes((HERE / file).read_bytes())
        header += f'\n#include "{initial_header}"\n'
    elif kind in search_hooks:
        hook = "static int replay_solve(PexaMan_t *p, int bound)"
        original = "int result = sat_solver_solve(p->pSat, NULL, NULL, 0, 0, 0, 0);"
        assert header.count(hook) == header.count(original) == 1
        filename, function = search_hooks[kind]
        if kind == "cofactor":
            (dest/"cofactor.h").write_bytes((HERE/"cofactor.h").read_bytes())
        if kind=="xor-proof":
            (dest/"xor_condition.h").write_bytes((HERE/"xor_condition.h").read_bytes())
        header = header.replace(hook,(HERE/filename).read_text()+"\n"+hook)
        header = header.replace(original, f"int result = {function}(q);")
    elif kind == "interval":
        (dest / "interval.h").write_bytes((HERE / "interval.h").read_bytes())
        hook = "static int replay_pair("
        original = "p9_joint_support(q->rows, q->target, ops, zeros, ones, domains, cap, charged, &result)"
        marker = "    replay_at_fixpoint = replay_visit;"
        done = "    replay_at_fixpoint = NULL;"
        assert all(header.count(s) == 1 for s in (hook, original, marker, done))
        header = header.replace(hook,(HERE / "interval_hook.h").read_text()+"\n"+hook)
        header = header.replace(original, "ff_support(q, obj, ops, zeros, ones, domains, cap, charged, &result)")
        header = header.replace(marker, "    ff_prepare(q);\n"+marker)
        header = header.replace(done,done+'\n    if (ff_stats) printf("FF_CALLS %llu %llu\\n", ff_calls, q->checks);')
    elif kind != "base":
        hook = "static int replay_solve(PexaMan_t *p, int bound)"
        marker = "    replay_at_fixpoint = replay_visit;"
        assert header.count(hook) == header.count(marker) == 1
        candidate = kind.startswith("candidate")
        units = ["candidate.h"] if candidate else []
        types = kind.startswith("types")
        if types:
            units.append("types.h")
            (dest/"gate_clauses.h").write_bytes((HERE/"gate_clauses.h").read_bytes())
        if kind.endswith("diagnostic"):
            units.append("diagnostic.h")
        if candidate:
            (dest / "projection.h").write_bytes((HERE / "projection.h").read_bytes())
        header = header.replace(hook, "\n".join((HERE / unit).read_text() for unit in units) + "\n" + hook)
        if kind.endswith("diagnostic"):
            replacement = "    ff_diagnostic_setup(q);\n    replay_at_fixpoint = ff_diagnostic_visit;"
        else:
            replacement = marker
        if candidate:
            replacement = "    if (!ff_add_clauses(q)) return l_False;\n" + replacement
        if types:
            replacement = "    if (!ff_add_types(q)) return l_False;\n" + replacement
        header = header.replace(marker, replacement)
    (dest / "joint_trail.h").write_text(header)
    patches = []
    for tag in ("compositions", "support", "joint-trail", "sat-trail"):
        path = dest / (tag + ".patch")
        # The pinned source archives use LF even in a Windows autocrlf checkout.
        path.write_bytes((ROOT / "variants" / path.name).read_bytes().replace(b"\r\n", b"\n"))
        patches.append(path)
    plugin_patches = patches[:-1]
    if kind in initial_hooks:
        _, filename = initial_hooks[kind]
        patch = dest / filename
        patch.write_bytes((HERE / filename).read_bytes().replace(b"\r\n", b"\n"))
        plugin_patches.append(patch)
    build(name, plugin_patches, patches[-1])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=("base", "diagnostic", "candidate", "candidate-diagnostic",
                                   "interval", "types", "types-diagnostic", "partition","xor-proof","cofactor","prefix","bounded","tail","library-check","library-check-fast","library-check-fixed"))
    compile_variant(p.parse_args().kind)
