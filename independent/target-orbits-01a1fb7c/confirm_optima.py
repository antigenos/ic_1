"""Replay two returned circuits and exhaust the strict lower bounds without SAT."""
import argparse
import json
from pathlib import Path
import time
from compare_orbits import HERE, ROOT
from repeat_0189 import pin
from lower_bound import cheaper_circuit
from witness import simulate


def read_circuit(directory, truth):
    packed=directory/"runs.jsonl"
    if packed.exists():
        rows=(json.loads(line) for line in packed.read_text().splitlines())
        matches=[r for r in rows if r["experiment"]["truth"]==truth and r["experiment"]["arm"]=="B"]
        record,=matches
        return record,record["solver_output"]
    path,=(directory/truth).glob("*-B/result.json")
    return json.loads(path.read_bytes()),path.with_name("solver.log").read_bytes().decode()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    packed=HERE/"evidence/full-300"
    parser.add_argument("--data",type=Path,default=packed if packed.exists() else ROOT/".local/orbit-confirmation-300")
    parser.add_argument("--cpu",type=int)
    args=parser.parse_args()
    if args.cpu is not None:
        pin(args.cpu)
    for t in ("0017","018b"):
        r,raw=read_circuit(args.data,t)
        witness=simulate(raw,4,int(t,16))
        assert r["status"]=="solver_completed_verified_witness" and witness==r["witness"]
        start=time.perf_counter()
        cheaper,states=cheaper_circuit(4,int(t,16),witness["activity"])
        proof=dict(truth=t,witness=witness,strict_upper=witness["activity"],cheaper_exists=cheaper,states=states)
        recorded=json.loads((HERE/f"evidence/additional-optima/{t}.json").read_bytes())
        assert proof=={k:recorded[k] for k in proof} and not cheaper
        proof.update(independent_wall_s=time.perf_counter()-start,cpu=args.cpu)
        print(json.dumps(proof),flush=True)
