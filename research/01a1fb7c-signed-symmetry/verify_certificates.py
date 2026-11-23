"""Replay every published bounded result and check consistency across thresholds."""
import json
from check_symmetry import HERE
from family import source
from witness import simulate


def main():
    members,history,_=source()
    confirm=json.loads((HERE/"confirmation/summary.json").read_bytes())
    for t,group in confirm["cases"].items():
        history[t].update(row["activity"] for row in group.values() if row["activity"] is not None)
    limits={}
    details={}
    for name in ("closure-302","closure-366","closure-440","raw-500","orbit-440","orbit-500",
                 "prefix-302","prefix-440","prefix-500","prefix-560"):
        data=json.loads((HERE/(name+".json")).read_bytes())
        limit=data["limit"]
        costs=data["certificates"]
        assert list(costs)==members and all(v is None or (0<=v<=limit and not v%2) for v in costs.values())
        if limit in limits:
            assert limits[limit]==costs
        limits[limit]=costs
        finite={t for t in members if costs[t] is not None}
        assert len(finite)==data["finite_minima"]
        matched=0
        for t,values in history.items():
            assert len(values)<=1
            if values:
                old=next(iter(values))
                assert costs[t]==(old if old<=limit else None)
                matched+=old<=limit
        assert matched==data["witnessed_minima_matched"]
        verified=0
        if "mode" in data:
            assert set(data["verified_circuits"])==finite
            for t,rec in data["verified_circuits"].items():
                w=simulate(rec["circuit"],4,int(t,16))
                assert w==rec["witness"] and w["activity"]==costs[t]
                verified+=1
        details[name]=dict(finite=len(finite),checked_circuits=verified,enumerated_states=data["states"])
    for lower,higher in zip(sorted(limits),sorted(limits)[1:]):
        for t in members:
            v=limits[higher][t]
            assert limits[lower][t]==(v if v is not None and v<=lower else None)
    assert details["closure-302"]["enumerated_states"]==16950
    assert details["closure-366"]["enumerated_states"]==196250
    return dict(functions=len(members),boundaries=sorted(limits),versions=details)


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
