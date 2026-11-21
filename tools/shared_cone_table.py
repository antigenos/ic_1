"""Generate the target-independent, reduced-domain exact side-input cost tables."""
import argparse
from itertools import combinations
from pathlib import Path

from probe_shared_predecessor import divisions, free_input_opt, normal, outcomes, project


def table():
    pins = (0xaaaa, 0xcccc, 0xf0f0, 0xff00)
    divisors = sorted({normal(project(h, rows)) for a, b in combinations(pins, 2)
                       for h in outcomes(a, b) for _, _, halves in divisions() for rows in halves})
    by_value = [divisors.index(v) if v in divisors else -1 for v in range(0, 256, 2)]
    indices = "static const signed char side_index[128] = {" + ",".join(map(str, by_value)) + "};"
    lines = ["/* Generated with tools/shared_cone_table.py. */", indices,
             "static const unsigned char side_opt[][128] = {"]
    for h in divisors:
        row = free_input_opt(h)
        lines.append("  {" + ",".join(str(row[x]) for x in range(0, 256, 2)) + "},")
    return "\n".join(lines + ["};", ""])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    source = table()
    if args.check:
        assert args.output.read_text() == source
    else:
        args.output.write_text(source, encoding="ascii")
