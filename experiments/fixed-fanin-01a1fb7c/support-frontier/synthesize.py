"""Recognize the first two activity levels directly and construct optimal circuits."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def set_bits(word):
    while word:
        low = word & -word
        yield low.bit_length()-1
        word ^= low


def classify(n, truth):
    rows = 1 << n
    if n < 4 or truth < 0 or truth.bit_length() > rows:
        raise ValueError("expected at least four inputs and a truth table of the specified width")
    mask = (1 << rows)-1
    complement = truth.bit_count() > rows//2
    minority = mask ^ truth if complement else truth
    count = minority.bit_count()
    if count == 1:
        return "minterm", complement, next(set_bits(minority)), (), ()
    if count == rows//2:
        for i in range(n):
            step = 1 << i
            literal = (mask // ((1 << step)+1)) << step
            delta = truth ^ literal
            phase = delta.bit_count() > rows//2
            if phase:
                delta ^= mask
            if delta.bit_count() == 2:
                first, second = set_bits(delta)
                if first ^ second == step:
                    return "parity", phase, first, (i,), tuple(j for j in range(n) if j!=i)
        return None
    if count < 3 or (count & (count+1)):
        return None
    k = (count+1).bit_length()-1
    seed = (minority & -minority).bit_length()-1
    varying = missing = 0
    for row in set_bits(minority):
        varying |= seed ^ row
        missing ^= row
    # The XOR of every vertex in a cube of dimension >=2 is zero.
    if varying.bit_count()!=k or k>=n:
        return None
    enable = tuple(i for i in range(n) if not ((varying>>i)&1))
    excluded = tuple(set_bits(varying))
    return "puncture", complement, missing, enable, excluded


class Circuit:
    def __init__(self, n):
        self.n = n
        self.gates = []

    def gate(self, a, b, op):
        ai, ap = a
        bi, bp = b
        code = sum(((op >> ((x ^ ap) + 2*(y ^ bp))) & 1) << (x+2*y)
                   for x in range(2) for y in range(2))
        phase = code & 1
        self.gates.append([ai, bi, code ^ (15 if phase else 0)])
        return self.n+len(self.gates)-1, phase

    def conjunction(self, wires):
        result, *rest = wires
        for signal in rest:
            result = self.gate(result,signal,8)
        return result


def solution(n, truth):
    shape = classify(n,truth)
    if shape is None:
        return None
    kind, complement, point, enable, excluded = shape
    rows = 1 << n
    def partial(t):
        return sum(2*(rows>>s)*(rows-(rows>>s)) for s in range(2,t+1))
    def matches(i):
        return i, 1 ^ ((point>>i)&1)
    def invert(signal):
        return signal[0], 1 ^ signal[1]
    endpoints = []
    sizes = ["size","activity"] if kind=="puncture" and len(enable)>=2 else ["both"]
    for objective in sizes:
        c = Circuit(n)
        activity = partial(n-1)
        if kind=="minterm":
            out = c.conjunction([matches(i) for i in range(n)])
        elif kind=="parity":
            selector = c.conjunction(list(map(matches,excluded)))
            out = c.gate((enable[0],0),selector,6)
        else:
            h = c.conjunction(list(map(matches,enable)))
            if objective=="activity":
                m = c.conjunction([h,*map(matches,excluded)])
                out = c.gate(h,invert(m),8)
                activity = partial(n)
            else:
                other = c.conjunction(list(map(matches,excluded)))
                out = c.gate(h,invert(other),8)
                activity = partial(len(enable))+partial(len(excluded))
        assert out[0]==n+len(c.gates)-1
        phase = int(out[1]) ^ int(complement)
        assert phase==truth&1
        endpoints.append(dict(objective=objective,gate_count=len(c.gates),activity=activity,
                              gates=c.gates,complement=phase))
    return dict(inputs=n,truth=format(truth,"x"),family=kind,endpoints=endpoints)


def native_row(n,truth,endpoint):
    if n!=4:
        raise ValueError("native DATE certificate entry accepts four inputs")
    gates = []
    for a,b,code in endpoint["gates"]:
        if a>b:
            code=(code&9)|((code&2)<<1)|((code&4)>>1)
        gates.append([max(a,b),min(a,b),code])
    return dict(truth=f"{truth:04x}", activity=endpoint["activity"],
                gates=gates, complement=endpoint["complement"], direct=-2)


def abc(binary,n,truth,answer,endpoint):
    if n!=4:
        raise ValueError("this author integration accepts four-input targets")
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from native_audit import spec, verify
    env={k:v for k,v in os.environ.items() if not k.startswith(("FF_","REPLAY_"))}
    if answer:
        chosen=next(x for x in answer["endpoints"] if x["objective"] in {"both",endpoint})
        row=native_row(n,truth,chosen)
        env["FF_LIBRARY"]=spec(row)
    run=subprocess.run([str(binary.resolve()),"-c",f"pexact -I 4 -M 2 {truth:04x}"],
                       env=env,check=True,capture_output=True,text=True)
    if answer:
        verify(row,run.stdout)
    return run.stdout


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n",type=int)
    parser.add_argument("truth",help="hex truth table, variable 0 changes fastest")
    parser.add_argument("--abc",type=Path,help="four-input DATE binary with FF_LIBRARY support")
    parser.add_argument("--endpoint",choices=("activity","size"),default="activity")
    args=parser.parse_args()
    target=int(args.truth,16)
    answer=solution(args.n,target)
    if args.abc:
        print(abc(args.abc,args.n,target,answer,args.endpoint),end="")
    else:
        print(json.dumps(answer or {"status":"outside_proved_family"}))
