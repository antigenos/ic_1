"""Live independent strict lower-bound checks on two additional completed targets."""
import json
from pathlib import Path
import sys
import time
from compare_orbits import HERE, ROOT
from repeat_0189 import pin
from lower_bound import cheaper_circuit
from witness import simulate


if __name__=="__main__":
    pin(10)
    dest=HERE/"evidence"/"additional-optima"
    dest.mkdir(parents=True,exist_ok=False)
    for t in ("0017","018b"):
        root=ROOT/".local/orbit-confirmation-300"/t
        records=list(root.glob("*-B/result.json"))
        assert len(records)==1
        r=json.loads(records[0].read_text())
        witness=simulate(records[0].with_name("solver.log").read_text(),4,int(t,16))
        assert witness==r["witness"]
        start=time.perf_counter()
        cheaper,states=cheaper_circuit(4,int(t,16),witness["activity"])
        proof=dict(truth=t,witness=witness,strict_upper=witness["activity"],cheaper_exists=cheaper,
                   states=states,independent_wall_s=time.perf_counter()-start,cpu=10)
        (dest/(t+".json")).write_text(json.dumps(proof,indent=2)+"\n")
        print(json.dumps(proof),flush=True)
        if cheaper:
            raise ValueError("Cheaper implementation found")
