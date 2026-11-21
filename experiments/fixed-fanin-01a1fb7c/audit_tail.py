"""Check all 208 budget-360 answers against an independent unordered-set oracle."""
import argparse
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile
from audit_bounded import replay, small_oracle

HERE = Path(__file__).resolve().parent


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("tail_checker", type=Path)
    p.add_argument("bounded_checker", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    small_checks = json.loads(subprocess.check_output([args.tail_checker.resolve()], text=True))
    costs, states = small_oracle(360)
    with ZipFile(HERE / "reproduction.zip") as z:
        cases = json.loads(z.read("evidence/e14-main/manifest.json"))["cases"]
    pairs = [(target, 360, 2000000, mode) for target in cases for mode in (0, 2)]
    pairs += [(target, 480, limit, mode) for target in ("0016", "0017")
              for limit in (2000000, 20000000) for mode in (0, 2)]
    data = "\n".join(f"{t} {cap} {limit} {mode}" for t,cap,limit,mode in pairs)
    output = subprocess.run([args.bounded_checker.resolve()], input=data, text=True, capture_output=True, check=True)
    rows = []
    for raw, (t, cap, limit, mode) in zip(output.stdout.splitlines(), pairs, strict=True):
        row = json.loads(raw)
        assert (row["truth"], row["cap"], row["work"], row["projected"]) == (t, cap, limit, mode)
        if row["found"]:
            replay(row)
        if cap == 360:
            key = int(t, 16)
            key ^= 65535 if key & 1 else 0
            assert row["complete"] and bool(row["found"]) == (key in costs)
            if key in costs:
                assert row["cost"] == costs[key]
        elif limit == 20000000 or mode == 2:
            assert row["complete"] and row["found"] and row["cost"] == {"0016":406,"0017":400}[t]
        rows.append(row)
    certs = [r["truth"] for r in rows if r["cap"]==360 and r["projected"]==2 and r["found"]]
    out = dict(three_input=small_checks, independent_states_360=states, certified_at_360=certs, cases=rows)
    args.output.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(len(certs), states)
