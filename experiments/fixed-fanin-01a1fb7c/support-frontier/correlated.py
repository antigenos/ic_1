"""Exact empirical-cost optimization within the two admitted circuit families."""
from synthesize import Circuit, classify, set_bits


def subsets(s):
    u=s
    while u:
        yield u
        u=(u-1)&s


def invert(expr):
    return ("not",expr)


def join(a,b):
    return ("and",a,b)


def materialize(n,point,expr,phase):
    c=Circuit(n)
    memo={}
    def emit(e):
        if e in memo:
            return memo[e]
        if isinstance(e,int):
            wire=e,1^((point>>e)&1)
        elif e[0]=="not":
            i,p=emit(e[1])
            wire=i,1^p
        else:
            wire=c.gate(emit(e[1]),emit(e[2]),8)
        memo[e]=wire
        return wire
    _,neg=emit(expr)
    return dict(gates=c.gates,complement=int(phase)^neg,gate_count=len(c.gates))


class Optimizer:
    def __init__(self,truth,values,pairs,arrivals):
        self.n=len(values)
        kind,self.phase,self.point,a,b=classify(self.n,truth)
        assert kind=="puncture" and min(len(a),len(b))>=2
        self.a=sum(1<<i for i in a)
        self.b=sum(1<<i for i in b)
        self.pairs=pairs
        self.low=(1<<pairs)-1
        self.mask=(1<<(2*pairs))-1
        self.arrivals=arrivals
        self.values={0:self.mask}
        for i,v in enumerate(values):
            self.values[1<<i]=v^(0 if (self.point>>i)&1 else self.mask)
        self.costs={}
        self.memo={}

    def conjunction(self,s):
        if s not in self.values:
            bit=s & -s
            self.values[s]=self.conjunction(s^bit)&self.values[bit]
        return self.values[s]

    def cost(self,s,mixed=False):
        key=(s,mixed)
        if key not in self.costs:
            v=self.conjunction(s)
            if mixed:
                v&=self.mask^self.conjunction(self.b)
            self.costs[key]=((v^(v>>self.pairs))&self.low).bit_count()
        return self.costs[key]

    def search(self,kind,s,deadline):
        key=(kind,s,deadline)
        if key not in self.memo:
            self.memo[key]=self.compute(kind,s,deadline)
        return self.memo[key]

    def compute(self,kind,s,deadline):
        if deadline<0:
            return None
        if kind in ("tree","chain") and s.bit_count()==1:
            i=s.bit_length()-1
            return (0,i) if self.arrivals[i]<=deadline else None
        if kind=="mixed" and s==0:
            result=self.search("tree",self.b,deadline)
            return (result[0],invert(result[1])) if result else None
        if kind=="extension" and s==0:
            return self.search("chain",self.a,deadline)
        best=None
        price=self.cost(s|self.a) if kind=="extension" else self.cost(s,kind=="mixed")
        if kind in ("chain","extension"):
            for i in set_bits(s):
                if self.arrivals[i]>=deadline:
                    continue
                rest=self.search(kind,s^(1<<i),deadline-1)
                if rest and (best is None or rest[0]+price<best[0]):
                    best=rest[0]+price,join(rest[1],i)
        else:
            for u in subsets(s):
                if kind=="tree" and (u==s or u>(s^u)):
                    continue
                left=self.search("tree",u,deadline-1)
                if left is None:
                    continue
                right=self.search(kind,s^u,deadline-1)
                if right:
                    c=left[0]+right[0]+price
                    if best is None or c<best[0]:
                        best=c,join(left[1],right[1])
        return best

    def endpoint(self,family,deadline):
        deadline=min(deadline,max(self.arrivals)+self.n)
        if family=="tree":
            best=self.search("mixed",self.a,deadline)
            if best is None:
                return None
            cost,expr=best
        else:
            best=self.search("extension",self.b,deadline-1)
            if best is None:
                return None
            cost,m=best
            h=m
            for _ in range(self.b.bit_count()):
                h=h[1]
            expr=join(h,invert(m))
            cost+=self.cost(self.a,True)
        ep=materialize(self.n,self.point,expr,self.phase)
        assert ep["gate_count"]==self.n-(family=="tree")
        return cost,ep


def path_lengths(n,ep):
    gates=ep["gates"]
    distance=[-1]*(n+len(gates))
    distance[-1]=0
    for i in reversed(range(len(gates))):
        a,b,_=gates[i]
        assert distance[n+i]>=0
        for j in (a,b):
            distance[j]=max(distance[j],distance[n+i]+1)
    assert min(distance[:n])>=1
    return distance[:n]


def transition_panels(inputs,ep,panel_width,panels):
    pairs=panel_width*panels
    field=(1<<panel_width)-1
    signals=list(inputs)
    totals=[0]*panels
    for a,b,op in ep["gates"]:
        x,y=signals[a],signals[b]
        if op==8: v=x&y
        elif op==2: v=x&~y
        elif op==4: v=y&~x
        elif op==14: v=x|y
        elif op==6: v=x^y
        else: raise ValueError(op)
        signals.append(v)
        toggles=v^(v>>pairs)
        for i in range(panels):
            totals[i]+=(toggles&field).bit_count()
            toggles>>=panel_width
    return totals
