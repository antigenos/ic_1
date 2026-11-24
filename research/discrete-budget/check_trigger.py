"""Check trigger/H equivalence for actual searches, including emitted clauses in order."""
import gzip
import argparse
import hashlib
import json
from build import HERE
from summary import diagnostic


def trace(prefix,truth,mode):
    guard_files=list((HERE/"results").glob(prefix+"-"+truth+"-a*/complete.json"))
    assert len(guard_files)==1
    path,=guard_files[0].parent.glob(truth+"-*-"+mode+"/solver.log.gz")
    lines=[l for l in gzip.decompress(path.read_bytes()).splitlines()
           if l.startswith((b"REASON ",b"WINDOW_BOUND ",b"JOINT ",b"WINDOW "))]
    return [l.split(b" seconds=")[0] for l in lines]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base-profile",default="dev2-profile")
    p.add_argument("--base-trace",default="dev2-trace")
    p.add_argument("--trigger-profile",default="dev3-trigger-profile")
    p.add_argument("--trigger-trace",default="dev3-trigger-trace")
    args=p.parse_args()
    hp=diagnostic(args.base_profile)
    tp=diagnostic(args.trigger_profile)
    tr=diagnostic(args.trigger_trace)
    out={}
    for truth in ("0189","0019"):
        a=trace(args.base_trace,truth,"holes")
        b=trace(args.trigger_trace,truth,"trigger")
        assert a==b
        h=hp[truth+"-holes"]
        t=tp[truth+"-trigger"]
        assert h["outer_sequence"]==t["outer_sequence"] and h["joint"]==t["joint"]
        assert all(h["cost"][k]==t["cost"][k] for k in ("decisions","propagations","reason_attempts"))
        assert t["cost"]["trigger_considered"]==h["cost"]["calls"]
        out[truth]=dict(identical_records=len(a),semantic_sha256=hashlib.sha256(b"\n".join(a)).hexdigest(),
                        holes=h["cost"],trigger=t["cost"],clauses=tr[truth+"-trigger"]["actual_reasons"])
    print(json.dumps(out,indent=2))


if __name__=="__main__":
    main()
