"""Verify classical symmetric-variable ordering on every archived completed network."""
import json
from check_orbits import HERE, GATE, group, image, normal, pins


def swaps(target):
    pairs=[]
    for i in range(3):
        for j in range(i+1,4):
            rows=tuple(r ^ (((r>>i ^ r>>j)&1)*((1<<i)|(1<<j))) for r in range(16))
            if image(target,rows)==target:
                pairs.append((i,j))
    return pairs


def main():
    family=json.loads((HERE/"orbit-check.json").read_text())["family"]
    strict=[t for t,d in family.items() if not swaps(int(t,16)) and d["signed"]<30]
    count=0
    for arm in ("author","support","both"):
        path=HERE/f"reproduction/evidence/e14-main/{arm}.jsonl"
        for line in path.read_text().splitlines():
            obs=json.loads(line)
            if "witness" not in obs:
                continue
            t=int(obs["experiment"]["truth"],16)
            first={x:999 for x in "abcd"}
            for g,_,a,b in GATE.findall(obs["solver_output"].replace("\r","")):
                for x in (a,b):
                    if x in first:
                        first[x]=min(first[x],int(g))
            assert max(first.values())<999
            masks=pins(4)
            for row in group(4,t,False):
                perm=[masks.index(normal(image(mask,row),65535)) for mask in masks]
                order=[first["abcd"[perm.index(j)]] for j in range(4)]
                if all(order[i]<=order[j] for i,j in swaps(t)):
                    break
            else:
                raise AssertionError(t)
            count+=1
    return dict(validated_witnesses=count,classes_with_no_swap_but_signed_first_gate_reduction=strict,
                number=len(strict))


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
