"""Compare a real frozen solver fixed point with exhaustive operand assignments."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from repeat_0189 import pin


def check(cpu, dest):
    pin(cpu)
    dest.mkdir(parents=True, exist_ok=False)
    binary = ROOT / ".local/variants/fixed-fanin-diagnostic" / ("abc.exe" if os.name == "nt" else "abc")
    records = []
    for i in range(4):
        env = {k: v for k, v in os.environ.items() if not k.startswith("REPLAY_")}
        env["FF_PRIMARY"] = str(i)
        result = subprocess.run([binary, "-c", "pexact -I 4 -M 2 0189"], env=env, cwd=dest,
                                capture_output=True, timeout=60, check=True)
        (dest / f"primary-{i}.log").write_bytes(result.stdout + result.stderr)
        lines = [s for s in result.stdout.decode().splitlines() if s.startswith("FF_ROOT ")]
        assert len(lines) == 1, (i, result.stdout[-400:])
        raw = dict(x.split("=") for x in lines[0].split()[1:])
        record = dict(primary=i, observed=raw)
        if raw["conflict"] == "0":
            assert (raw["decisions"],raw["queue"],raw["chosen"],raw["high"]) == ("0","1","1","1"), raw
            h = sum((r >> i & 1) << r for r in range(16))
            allowed = [g for g in range(0, 65536, 2)
                       if 0xfe76 in (g & h, g & ~h, ~g & h, g ^ h, g | h)]
            assert allowed == [0xfe76 ^ h]
            g = allowed[0]
            z, o = int(raw["zeros"],16), int(raw["ones"],16)
            assert not ((z & g) | (o & (65535 ^ g)))
            folded = min(g.bit_count(),16-g.bit_count())
            record.update(partner=f"{g:04x}", forced_rows_missing=16-(z|o).bit_count(),
                          unsupported_counts_open=(int(raw["domain"],16) & ~(1<<folded)).bit_count())
        records.append(record)
    output = dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), cpu=cpu,
                  normalized_target="fe76", gates=4, upper=300, records=records)
    (dest / "audit.json").write_text(json.dumps(output, indent=2)+"\n")
    return output


if __name__ == "__main__":
    print(json.dumps(check(int(sys.argv[1]), Path(sys.argv[2]).resolve()), indent=2))
