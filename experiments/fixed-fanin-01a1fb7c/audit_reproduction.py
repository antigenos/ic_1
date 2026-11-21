"""Replay the archived 208-case comparison, ablations and independent small proofs."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/"tools"))
from audit_batch import audit
from lower_bound import cheaper_circuit
from witness import simulate


def source_check(directory):
    specs = json.loads((ROOT/"sources.json").read_text())
    checked = {}
    paths = {"abc": ("src/sat/bsat/satSolver.c","abc/src/sat/bsat/satSolver.c"),
             "pexact": ("pexact.c","abc/src/ext-pexact/pexact.c"),
             "tcjap": ("src/joint_relation.c","reference/src/joint_relation.c")}
    for name, (component, local) in paths.items():
        archive = directory/(name+".tar.gz")
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source,"sha256").hexdigest()
        assert digest == specs[name]["archive_sha256"]
        with tarfile.open(archive) as tar:
            matches = [m for m in tar.getmembers() if m.name.partition("/")[2] == component]
            assert len(matches)==1 and matches[0].name.partition("/")[0].endswith(specs[name]["commit"])
            upstream = tar.extractfile(matches[0]).read()
        assert upstream == (ROOT/".local"/local).read_bytes()
        checked[name] = dict(commit=specs[name]["commit"], archive_sha256=digest,
                             component_sha256=hashlib.sha256(upstream).hexdigest())
    return checked


def run():
    with TemporaryDirectory() as temp, ZipFile(HERE/"reproduction.zip") as archived:
        folder = Path(temp)
        assert all((folder/name).resolve().is_relative_to(folder.resolve()) for name in archived.namelist())
        archived.extractall(folder)
        evidence = folder/"evidence"
        groups = {}
        for name in ("e14-main","e14-ablation"):
            result = audit(evidence/name)
            assert result == json.loads((evidence/name/"audit.json").read_text())
            groups[name] = {k:v for k,v in result.items() if k!="comparisons"}
        proofs = {}
        for tag, n, truth in (("baseline-0189",4,0x189),("baseline-xor3",3,0x96)):
            d = evidence/tag
            witness = simulate((d/"solver.log").read_text(),n,truth)
            assert witness == json.loads((d/"result.json").read_text())["witness"]
            cheaper, states = cheaper_circuit(n,truth,witness["activity"])
            assert not cheaper and states == json.loads((d/"lower_bound.json").read_text())["states"]
            proofs[tag] = dict(optimum=witness["activity"],states=states)
        boundary = json.loads((evidence/"e14-boundary.json").read_text())
        assert len(boundary)==14
        proved=0
        for row in boundary:
            if len(row["essential_inputs"])!=3:
                continue
            t=int(row["reduced"],16)
            for result in row["reduced_runs"].values():
                assert simulate(result["solver_output"],3,t)==result["witness"]
                assert result["witness"]["activity"]==row["reduced_optimum"]
            cheaper, states=cheaper_circuit(3,t,row["reduced_optimum"])
            assert not cheaper and states==row["strict_bound_states"]
            proved+=1
        assert proved==10
        return dict(groups=groups,small_optima=proofs,three_input_boundary_proofs=proved)


if __name__=="__main__":
    result=run()
    if len(sys.argv)>1:
        result["sources"]=source_check(Path(sys.argv[1]))
    if len(sys.argv)>2:
        Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
