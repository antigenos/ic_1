"""Audit the frozen experiment records and print every circuit's paired result."""
from collections import Counter
import json
from pathlib import Path
import statistics
from application import DESIGNS, VERSION
from audit import check_witness, compare_reference

HERE=Path(__file__).resolve().parent
E=HERE/"evidence"


def read(name):
    return json.loads((E/name).read_text())


def table(row):
    assert row["terminal"]=="complete" and row["witness_audit"]
    for w in row["witnesses"]:
        check_witness(row["n"],w)
    return {int(w["rep"],16):w["cost"] for w in row["witnesses"]}


def audit():
    for prefix,n,cap in (("discovery",4,360),("discovery",5,852),("held",5,1050),("held",6,3664)):
        records=[read(f"{prefix}-{n}-{cap}-{i}.json") for i in range(3)]
        assert {r["binary_sha256"] for r in records}=={records[0]["binary_sha256"]}
        targets=list(map(table,records))
        assert targets[0]==targets[1]==targets[2]
        compare_reference(n,cap,targets[2])
    for name in ("small-4-240","held-5-1050-2","held-6-3664-2"):
        independent=read(f"postfix-{name}.json")
        assert independent["status"]=="all_optima_identical" and independent["classes"]==len(table(read(name+".json")))
    for n,cap in ((3,96),(4,240),(4,150),(4,152),(4,180),(4,182)):
        row=read(f"small-{n}-{cap}.json")
        compare_reference(n,cap,table(row))
    report=read("pareto-audit.json")
    assert report["all_four_tables"]==65536 and report["independent_tree_cases"]==80
    assert all("FF_ORIGINAL_CNF verified" in log for log in report["native"].values())
    assert len(report["native"])==7 and "Switching Activity=208" in report["native_outside_fallback"]
    native=read("native-entry.json")
    assert native["targets"]==416 and len(native["batches_wall_s"])==13
    for pair in native["pairs"]:
        a,b=(pair["observations"][key]["witness"] for key in ("frozen","candidate"))
        assert a["truth"]==b["truth"]==pair["truth"] and a["activity"]==b["activity"]
    exact=read("correlated-small.json")
    assert exact["all_matched"] and exact["optimum_deadline_checks"]==394


def benchmark():
    files=sorted((E/"epfl").glob("*.json"))
    assert {x.stem for x in files}=={s for names in DESIGNS.values() for s in names.split()}
    totals=[0,0,0]
    area=[0,0,0]
    panels=[[0,0,0] for _ in range(8)]
    counts=Counter()
    wall=0.
    local=[0.,0.,0.]
    for file in files:
        r=json.loads(file.read_text())
        assert r["version"]==VERSION and r["cpu"]==24 and r["pairs_per_panel"]==512
        assert r["area"][2]-r["area"][1]==r["cuts"] and r["area"][0]==r["area"][1]
        assert len(r["panels"])==8 and all(len(row)==3 and min(row)>=0 for row in r["panels"])
        assert sum(r["widths"].values())==r["cuts"]
        for eq in r["equivalence"].values():
            if r["cuts"]:
                assert "Networks are equivalent" in eq["output"]
            else:
                assert eq=={"identity":True}
        scores=list(map(sum,zip(*r["panels"])))
        if not r["cuts"]:
            assert len(set(scores))==1 and len(set(r["depth"]))==1
        counts["changed"]+=bool(r["cuts"])
        counts["improved"]+=scores[2]<scores[1]
        counts["worse"]+=scores[2]>scores[1]
        counts["tied"]+=scores[2]==scores[1]
        counts["depth_increases"]+=r["depth"][2]>r["depth"][1]
        counts["cuts"]+=r["cuts"]
        wall+=r["wall_s"]
        for i in range(3):
            totals[i]+=scores[i]
            area[i]+=r["area"][i]
            local[i]+=r["local_uniform_sum"][i]
            for j in range(8):
                panels[j][i]+=r["panels"][j][i]
        print(file.stem,r["cuts"],r["area"],r["depth"],scores,
              f"{100*(1-scores[2]/scores[1]):.4f}%")
    paired_pct=[100*(1-c/b) for _,b,c in panels]
    print(json.dumps(dict(counts=counts,transitions=totals,area=area,local=local,
                          panel_pct=paired_pct,mean_panel_pct=statistics.mean(paired_pct),
                          wall_s=wall),indent=2))


def transfer():
    files=sorted((E/"transfer").glob("*.json"))
    assert {x.stem for x in files}=={s for names in DESIGNS.values() for s in names.split()}
    counts=Counter()
    area=[0]*3
    panels=[[0]*3 for _ in range(8)]
    wall=fit=0.
    print("Design / size changes / additional sharing / depths / held-out changes / relative gain over size control")
    for path in files:
        r=json.loads(path.read_text())
        baseline=read(f"epfl/{path.name}")
        assert r["cut_sha256"]==baseline["cut_sha256"] and r["source_sha256"]==baseline["input_sha256"]
        assert r["cuts"]==baseline["cuts"] and r["areas"][:2]==baseline["area"][:2]
        assert r["areas"][2]-r["areas"][1]==r["sharing_changes"]
        assert r["depths"][0]>=r["depths"][1]>=r["depths"][2]
        assert r["pairs_per_panel"]==1024 and len(r["panels"])==8
        for j in range(2):
            assert r["training_counts"][j]-r["training_counts"][j+1]==sum(r["training_savings"][j])
            assert all(c>=0 for c in r["training_savings"][j])
            eq=r["equivalence"][j]
            assert ("Networks are equivalent" in eq["output"]) if r["cuts"] else eq=={"identity":True}
        scores=list(map(sum,zip(*r["panels"])))
        for i in range(3):
            area[i]+=r["areas"][i]
            for j in range(8): panels[j][i]+=r["panels"][j][i]
        counts["cuts"]+=r["cuts"]
        counts["tree_changes"]+=r["size_changes"]
        counts["sharing_changes"]+=r["sharing_changes"]
        counts["improved"]+=scores[2]<scores[1]
        counts["worse"]+=scores[2]>scores[1]
        counts["tied"]+=scores[2]==scores[1]
        counts["improved_original"]+=scores[2]<scores[0]
        counts["worse_original"]+=scores[2]>scores[0]
        counts["tied_original"]+=scores[2]==scores[0]
        wall+=r["total_s"]
        fit+=r["fit_s"]
        print(path.stem,r["size_changes"],r["sharing_changes"],r["depths"],scores,
              f"{100*(1-scores[2]/scores[1]):.4f}%")
    total=list(map(sum,zip(*panels)))
    print(json.dumps(dict(counts=counts,transitions=total,area=area,panels=panels,
                          aggregate_vs_control_pct=100*(1-total[2]/total[1]),
                          aggregate_vs_original_pct=100*(1-total[2]/total[0]),
                          panel_vs_control_pct=[100*(1-row[2]/row[1]) for row in panels],
                          fit_s=fit,total_s=wall),indent=2))


if __name__=="__main__":
    audit()
    benchmark()
    transfer()
