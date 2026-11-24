"""Audit raw rows, circuit bounds, diagnostic parity and paired end-to-end cost."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from witness import simulate

# Blob 5e60e50a21dd94da0c10247066785e45b478dd59 of the independent
# interval-proof branch at 5400328802c98c1870fb7f61ff2475f698ee48ea.
BOUNDS = {'0189':304,'0019':310,'0696':344,'0007':182,'07f8':216,
          '01ab':248,'1be4':320,'01ef':264,'03dc':326}
DEV = list(BOUNDS)[:3]
TEST = list(BOUNDS)[3:]
def read(path):
    return json.loads(path.read_bytes())

def examine(batch,ts,diagnostic,full_order=None):
    host = read(batch/'host.json')
    assert host['returncode']==0 and host['scans'] and not host['clashes']
    meta = read(batch/'freeze.json')
    output = {}
    for i,t in enumerate(ts):
        if full_order is not None: i=full_order.index(t)
        order = 'ABC'[i%3:]+'ABC'[:i%3]
        order = order if diagnostic else order+order[::-1]
        arms = {m:[] for m in 'ABC'}
        for j,m in enumerate(order,1):
            path = batch/t/f'{j}-{m}'
            row = read(path/'result.json')
            assert row['binary_sha256']==meta['hashes']['audit' if diagnostic else m]
            assert row['child_affinity']==[meta['cpu']]
            assert row['experiment']==dict(truth=t,arm=m,order=j,cpu=meta['cpu'])
            assert row['command'][1:]==['-c',f'pexact -I 4 -M 2 {t}']
            assert row['timeout_s']==(90 if diagnostic else 30)
            ok = row['status']=='solver_completed_verified_witness'
            assert ok or row['status']=='timeout'
            record = dict(complete=ok,wall=row['wall_s'],cap=row['capped_wall_s'])
            if ok:
                log = (path/'solver.log').read_text()
                witness = simulate(log,4,int(t,16))
                assert row['returncode']==0 and witness==row['witness'] and witness['activity']==BOUNDS[t]
                record['network']=[s for s in log.splitlines() if " = 4'b" in s]
            if ok and diagnostic:
                qs=read(path/'queries.json')
                assert qs and all(q['result'] in (-1,1) for q in qs)
                record['qs']=qs
            arms[m].append(record)
        output[t]=arms
    return output

def diagnostic_summary(rows):
    data={}
    for t,arms in rows.items():
        panel={}
        for m,records in arms.items():
            qs=records[0]['qs']
            panel[m]=dict(queries=len(qs),enabled=sum(q['enabled'] for q in qs),
                          decisions=sum(q['decisions'] for q in qs),conflicts=sum(q['conflicts'] for q in qs),
                          feature_us=sum(q['feature_ticks']/q['hz'] for q in qs)*1e6,
                          injection_us=sum(q['injection_ticks']/q['hz'] for q in qs)*1e6,
                          first_joint=[q['first_joint'] for q in qs],
                          first_conflict=[q['first_conflict'] for q in qs])
        # Compare the entire ordered diagnostic trace on uniformly selected arms.
        c=panel['C']
        parity='A' if c['enabled']==0 else 'B' if c['enabled']==c['queries'] else None
        if parity:
            def trajectory(m):
                return [{k:v for k,v in q.items() if k not in ('feature_ticks','injection_ticks','enabled')}
                        for q in arms[m][0]['qs']]
            assert trajectory(parity)==trajectory('C') and arms[parity][0]['network']==arms['C'][0]['network']
        if t=='0696': assert parity=='A'
        data[t]=dict(arms=panel,exact_parity=parity)
    return data

def timing_summary(rows):
    totals={}
    for m in 'ABC':
        rs=[row for arms in rows.values() for row in arms[m]]
        totals[m]=dict(completed=sum(r['complete'] for r in rs),runs=len(rs),
            classes=sum(all(r['complete'] for r in a[m]) for a in rows.values()),N=len(rows),
            capped=sum(r['cap'] for r in rs),
            by_order=[sum(a[m][j]['cap'] for a in rows.values()) for j in range(2)])
    common={}
    for m in 'AB':
        ts=[t for t,a in rows.items() if all(r['complete'] for k in (m,'C') for r in a[k])]
        common[m]=dict(classes=ts,runs=2*len(ts),wall={k:sum(r['wall'] for t in ts for r in rows[t][k]) for k in (m,'C')})
    per={t:{m:[r['cap'] for r in a[m]] for m in 'ABC'} for t,a in rows.items()}
    return dict(groups=totals,common=common,per_class=per,
                regressions={m:[t for t,arms in per.items() if sum(arms['C'])>1.05*sum(arms[m])] for m in 'AB'})

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('part',choices=['dev','holdout'])
    p.add_argument('kind',choices=['timed','audit'])
    p.add_argument('--batch',default='1')
    args=p.parse_args()
    diag=args.kind=='audit'
    data=examine(HERE/'raw'/f'{args.part}-{args.kind}-{args.batch}',DEV if args.part=='dev' else TEST,diag)
    print(json.dumps(diagnostic_summary(data) if diag else timing_summary(data),indent=2))
