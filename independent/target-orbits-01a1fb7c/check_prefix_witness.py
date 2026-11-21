"""Construct and independently simulate full networks for each strict conditional witness."""
from itertools import combinations
import json
from check_orbits import HERE, OPS, image, normal, op, pins


def check(target, proof):
    target = normal(target,65535)
    columns = proof["columns"]
    row = tuple(proof["row_permutation"])
    mapping = proof["column_permutation"]
    assert sorted(row)==list(range(16)) and len(set(columns))==6
    assert {mapping[i] for i in proof["required"]}==set(proof["required"])
    assert all(normal(image(g,row),65535)==columns[mapping[i]] for i,g in enumerate(columns))
    values = pins(4)
    net = []
    def append(a,b,code):
        assert a!=b and max(a,b)<len(values) and code in OPS
        t=op(code,values[a],values[b])
        assert t and not (t & 1)
        net.append((a,b,code))
        values.append(t)
        return len(values)-1
    i,j=proof["first_pins"]
    append(i,j,6)
    append(4,proof["second_primary"],proof["second_op"])
    assert values==columns
    a,b,c=next((a,b,c) for a,b in combinations(range(6),2) for c in OPS
               if op(c,values[a],values[b])==proof["third"])
    append(a,b,c)
    monomials={1<<j:j for j in range(4)}
    def monomial(m):
        if m not in monomials:
            bit=m & -m
            monomials[m]=append(monomial(m ^ bit),monomial(bit),8)
        return monomials[m]
    terms=[monomial(m) for m in range(1,16) if
           sum((target>>r)&1 for r in range(16) if (r&m)==r)%2]
    root,*rest=terms
    for t in rest:
        root=append(root,t,6)
    for g in (4,5,6):
        root=append(append(root,g,6),g,6)
    assert values[root]==target
    assert len(values)<=32
    rewired=list(net[:2])
    new_vals=list(columns)
    for n,(a,b,c) in enumerate(net[2:],6):
        pa=(values[a]>>row[0])&1
        pb=(values[b]>>row[0])&1
        pg=(values[n]>>row[0])&1
        c2=sum((((c>>((((v>>1)^pa)<<1)|((v&1)^pb)))&1)^pg)<<v for v in range(4))
        aa=mapping[a] if a<6 else a
        bb=mapping[b] if b<6 else b
        assert aa!=bb and c2 in OPS
        rewired.append((aa,bb,c2))
        new_vals.append(op(c2,new_vals[aa],new_vals[bb]))
        assert new_vals[-1]==normal(image(values[n],row),65535)
    def cost(signals):
        return [2*x.bit_count()*(16-x.bit_count()) for x in signals[4:-1]]
    for candidate in (net,rewired):
        assert {a for i,j,c in candidate for a in (i,j)}==set(range(len(values)-1))
    assert new_vals[6]==proof["representative"] and new_vals[-1]==target
    assert cost(values)==cost(new_vals)
    return dict(gates=len(net),activity=sum(cost(values)),before=net,after=rewired,
                all_inputs_and_internal_gates_used=True)


if __name__=="__main__":
    data=json.loads((HERE/"prefix-check.json").read_text())
    print(json.dumps({t:check(int(t,16),r["witness"]) for t,r in data.items()},indent=2))
