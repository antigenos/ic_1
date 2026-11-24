"""Map three EPFL designs, expand their four-input LUTs and verify whole-netlist equivalence."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time

from audit import HERE, PINS, normal, read_table, rebuild, representative, simulate
from witness import GATE

ROOT=HERE.parents[2]
ABC=ROOT/'.local/abc'/('abc.exe' if os.name=='nt' else 'abc')
REV='82d8cc6910419298e713a46644ed59fd3df53038'
SOURCES={'adder':('arithmetic','08d4902faaaa4f55616d0e5288e4d583a8e219c4'),
         'priority':('random_control','6d25253a36a3a378c4a25a522f9406409f091fda'),
         'router':('random_control','46f1176a3707c7926e6a236701f01c7d330c18a4')}


def abc(command):
    p=subprocess.run([str(ABC),'-c',command],cwd=ROOT,capture_output=True,text=True,check=True)
    return p.stdout+p.stderr


def rel(path):
    return path.relative_to(ROOT).as_posix()


def truth4(cubes):
    vals={int(line.split()[1]) for line in cubes}
    if len(vals)!=1:
        raise ValueError('expected an on-set or off-set cover')
    value=vals.pop()
    truth=0 if value else 65535
    for cube in cubes:
        pattern=cube.split()[0]
        for x in range(16):
            if all(c=='-' or int(c)==((x>>i)&1) for i,c in enumerate(pattern)):
                if value: truth |= 1<<x
                else: truth &= ~(1<<x)
    return truth


def essential(t):
    return all(any(((t>>r)^(t>>(r^(1<<i))))&1 for r in range(16)) for i in range(4))


def area_circuit(t, max_gates):
    logs=[]
    for size in range(3,max_gates+1):
        log=abc(f'twoexact -I 4 -N {size} {t:04x}')
        logs.append(log)
        if 'The problem has no solution.' in log: continue
        gates=sorted((int(g),int(code,2),a,b) for g,code,a,b in GATE.findall(log.replace('\r','')))
        if len(gates)!=size: raise ValueError(log)
        wires={chr(97+i):v for i,v in enumerate(PINS)}
        score=0
        for k,(g,code,a,b) in enumerate(gates):
            val=sum(((code>>(2*((wires[a]>>x)&1)+((wires[b]>>x)&1)))&1)<<x for x in range(16))
            wires[f'{g:02d}']=val
            if k+1<size: score+=2*val.bit_count()*(16-val.bit_count())
        text=(f'Realization of given 4-input function using {size} two-input gates complementary={t&1}:\n'+
              '\n'.join(m.group(0) for m in GATE.finditer(log.replace('\r','')))+f'\nSwitching Activity={score}')
        return text,simulate(text,4,t),''.join(logs)
    raise ValueError(f'No area solution within the verified feasible gate count for {t:04x}')


def emit(text, pins, output, block):
    names=dict(zip('abcd',pins))
    gates=sorted((int(i),op,a,b) for i,op,a,b in GATE.findall(text))
    lines=[]
    for index,(i,op,a,b) in enumerate(gates):
        wire=output if index==len(gates)-1 else f'cf_cut_{block}_{i}'
        lines.append(f'.names {names[a]} {names[b]} {wire}')
        lines.extend(f'{x:02b} 1' for x in range(4) if (int(op,2)>>x)&1)
        names[f'{i:02d}']=wire
    return lines


def run_one(name, rows, local):
    begin=time.perf_counter()
    source=ROOT/f'.local/downloads/epfl-{name}.aig'
    category,expected=SOURCES[name]
    blob=subprocess.check_output(['git','hash-object','--',str(source)],cwd=ROOT,text=True).strip()
    if blob!=expected: raise ValueError(f'{name} input hash {blob}')
    mapped=local/f'{name}-mapped.blif'
    command=f'read_aiger {rel(source)}; strash; if -K 4; write_blif {rel(mapped)}'
    abc(command)
    lines=mapped.read_text().replace('\\\n',' ').splitlines()
    assert not any('cf_cut_' in line for line in lines)
    mapped_s=time.perf_counter()-begin
    original=[]
    i=0
    cuts=Counter()
    while i<len(lines):
        hdr=lines[i]
        i+=1
        cubes=[]
        if hdr.startswith('.names '):
            while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('.','#')):
                cubes.append(lines[i].strip())
                i+=1
        fields=hdr.split()
        t=truth4(cubes) if len(fields)==6 and fields[0]=='.names' and cubes else None
        if t is not None and essential(t): cuts[t]+=1
        else: t=None
        original.append((hdr,cubes,t))
    results={}
    opt_cache={}
    for method in ('activity','area'):
        start=time.perf_counter()
        cache={}
        expanded=[]
        for idx,(hdr,cubes,t) in enumerate(original):
            if t is None:
                expanded.extend([hdr,*cubes])
                continue
            if t not in cache:
                if method=='activity':
                    row=rows[representative(normal(t))]
                    if row.upper!=row.lower: raise ValueError('cut has no exact certificate')
                    text,details=rebuild(t,row.raw,row.state)
                    opt_cache[t]=details
                else:
                    text,details,logs=area_circuit(t,opt_cache[t]['gates'])
                    (local/f'{name}-{t:04x}-area.log').write_text(logs)
                cache[t]=(text,details)
            fields=hdr.split()
            expanded.extend(emit(cache[t][0],fields[1:-1],fields[-1],idx))
        out=local/f'{name}-{method}.blif'
        out.write_text('\n'.join(expanded)+'\n')
        constructed=time.perf_counter()
        cec=abc(f'cec {rel(source)} {rel(out)}')
        ceclog=cec.strip()
        if not re.search(r'Networks are equivalent\b',ceclog) or 'NOT EQUIVALENT' in ceclog.upper():
            raise ValueError(ceclog)
        results[method]=dict(expansion_s=constructed-start,cec_s=time.perf_counter()-constructed,
                 charged_activity=sum(cuts[t]*v[1]['activity'] for t,v in cache.items()),
                 two_input_gates=sum(cuts[t]*v[1]['gates'] for t,v in cache.items()),
                 cec=ceclog,netlist_sha256=sha256(out.read_bytes()).hexdigest(),
                 per_truth={f'{t:04x}':dict(copies=cuts[t],**v[1]) for t,v in cache.items()})
    assert results['activity']['charged_activity']<=results['area']['charged_activity']
    return dict(benchmark=name,source=f'https://github.com/lsils/benchmarks/blob/{REV}/{category}/{name}.aig',
                blob=blob,command=command,mapping_s=mapped_s,lookup_nodes=sum(h.startswith('.names ') for h,_,_ in original),
                essential_4lut=sum(cuts.values()),distinct_truths=len(cuts),
                distinct_classes=len({representative(normal(t)) for t in cuts}),arms=results,
                combined_audit_wall_s=time.perf_counter()-begin)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('table',type=Path)
    p.add_argument('out',type=Path)
    args=p.parse_args()
    local=ROOT/'.local'/args.out.stem
    local.mkdir(exist_ok=False)
    if args.out.exists(): raise FileExistsError(args.out)
    _,rows=read_table(args.table)
    out=[run_one(name,rows,local) for name in SOURCES]
    args.out.write_text(json.dumps(dict(table_sha256=sha256(args.table.read_bytes()).hexdigest(),
                                    abc_sha256=sha256(ABC.read_bytes()).hexdigest(),designs=out),indent=2))
    for r in out:
        print(r['benchmark'],r['essential_4lut'],[x['charged_activity'] for x in r['arms'].values()])
