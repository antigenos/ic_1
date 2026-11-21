"""Audit the published freeze independently from the research working directory."""
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from audit_batch import audit
from lower_bound import cheaper_circuit
from witness import simulate


def main():
    archive = HERE/"date-tcjap-reproduction.zip"
    summaries = {}
    with TemporaryDirectory() as tmp, ZipFile(archive) as z:
        assert z.comment.decode()=="365a8db35e39918d10e9a16cec1495611dd5e0d0"
        expected = {"abc":"c851fce40d9dde1aaf32b087a0f449751ea070dc","pexact":"7253861c224e7c9de2c802e61c86f89338253544",
                    "tcjap":"59e5a0e954d6a0a6711b2bdc9898db875ede6889"}
        assert {k:v["commit"] for k,v in json.loads(z.read("sources.json")).items()}==expected
        for name in ("e14-main","e14-ablation"):
            folder="evidence/"+name+"/"
            for f in z.namelist():
                if f.startswith(folder) and not f.endswith("/"):
                    z.extract(f,tmp)
            actual = audit(Path(tmp)/folder)
            assert actual==json.loads(z.read(folder+"audit.json"))
            summaries[name]={k:v for k,v in actual.items() if k!="comparisons"}
        for label,t,n,score in (("baseline-0189","0189",4,304),("baseline-xor3","96",3,32)):
            original = z.read("evidence/"+label+"/solver.log").decode()
            assert simulate(original,n,int(t,16))["activity"]==score
            cheaper,states = cheaper_circuit(n,int(t,16),score)
            assert not cheaper
            summaries[label] = dict(optimum=score,strictly_cheaper_states=states)
    return dict(archive_sha256=sha256(archive.read_bytes()).hexdigest(),**summaries)


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
