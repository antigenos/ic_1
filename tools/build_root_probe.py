"""Build a diagnostics-only version of the frozen integration, with the same search decisions."""
from pathlib import Path

from build_variant import ROOT, build


def main():
    dest = ROOT / ".local/variants/cofactor-probe"
    dest.mkdir(parents=True, exist_ok=True)
    original = (ROOT / "tools/joint_trail.h").read_text()
    hook = "    replay_at_fixpoint = replay_visit;"
    entry = "static int replay_solve(PexaMan_t *p, int bound)"
    assert original.count(hook) == original.count(entry) == 1
    diagnostic = (ROOT / "tools/cofactor_root_probe.h").read_text()
    source = original.replace(entry, diagnostic + "\n" + entry)
    source = source.replace(hook, "    replay_at_fixpoint = probe_after_joint;")
    (dest / "joint_trail.h").write_text(source)
    patches = [ROOT / "variants" / (s + ".patch") for s in ("compositions", "support", "joint-trail")]
    build("cofactor-probe", patches, ROOT / "variants/sat-trail.patch")


if __name__ == "__main__":
    main()
