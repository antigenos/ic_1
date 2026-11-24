"""Paired stable-level switching on the actual expanded EPFL networks; no physical delays."""
import argparse
from hashlib import sha256, shake_256
import json
from pathlib import Path

from circuits import ROOT, SOURCES

LENGTH=65536
MASK=(1<<LENGTH)-1


def evaluate(netlist,design):
    lines=netlist.read_text().replace('\\\n',' ').splitlines()
    inputs=[]
    primary_outputs=[]
    nodes={}
    i=0
    while i<len(lines):
        fields=lines[i].split()
        i+=1
        if not fields: continue
        if fields[0]=='.inputs': inputs=fields[1:]
        if fields[0]=='.outputs': primary_outputs=fields[1:]
        if fields[0]!='.names': continue
        pins,out=fields[1:-1],fields[-1]
        if out in nodes: raise ValueError(f'duplicate node {out}')
        cubes=[]
        while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('.','#')):
            cube=lines[i].split()
            i+=1
            pattern,value=cube if pins else ('',cube[0])
            if len(pattern)!=len(pins): raise ValueError(cube)
            cubes.append((pattern,int(value)))
        nodes[out]=(pins,cubes)
    values={p:int.from_bytes(shake_256(f'epfl-stable-v1/{design}/{p}'.encode()).digest(LENGTH//8),'little')
            for p in inputs}

    def signal(name):
        if name in values: return values[name]
        pins,cubes=nodes[name]
        args=[signal(p) for p in pins]
        on=0
        levels={v for _,v in cubes}
        if len(levels)>1: raise ValueError('mixed cover')
        for pattern,_ in cubes:
            product=MASK
            for bit,x in zip(pattern,args):
                if bit=='1': product &= x
                elif bit=='0': product &= MASK^x
                elif bit!='-': raise ValueError(pattern)
            on |= product
        values[name]=(MASK^on) if levels=={0} else on
        return values[name]

    counts={k:((signal(k)^(signal(k)>>1)) & (MASK>>1)).bit_count() for k in nodes}
    outputs={name:sha256(signal(name).to_bytes(LENGTH//8,'little')).hexdigest()
             for name in primary_outputs}
    return counts,outputs


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('netlists',type=Path)
    p.add_argument('out',type=Path)
    args=p.parse_args()
    ds=[]
    for name in SOURCES:
        count1,out1=evaluate(args.netlists/f'{name}-area.blif',name)
        count2,out2=evaluate(args.netlists/f'{name}-activity.blif',name)
        assert out1==out2
        static1={k:v for k,v in count1.items() if not k.startswith('cf_cut_')}
        static2={k:v for k,v in count2.items() if not k.startswith('cf_cut_')}
        assert static1==static2
        a,b=sum(count1.values()),sum(count2.values())
        ds.append(dict(design=name,vectors=LENGTH,transitions_per_wire=LENGTH-1,
                       area_first=a,activity_first=b,relative_change=(b-a)/a,
                       shared_boundary_toggles=sum(static1.values()),outputs_matched=len(out1)))
    args.out.write_text(json.dumps(ds,indent=2))
    print(json.dumps(ds))
