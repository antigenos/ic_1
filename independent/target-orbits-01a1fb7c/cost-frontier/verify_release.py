"""Replay completed proof tables and functional checks; summarize comparable measurement scopes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from audit import HERE, STUDY, audit, simulate


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def check_library(folder):
    receipt=read(folder/'result.json')
    raw=folder/'table.tsv'
    if digest(raw)!=receipt['table_sha256'] or receipt['exit_code']!=0:
        raise ValueError(folder)
    meta,rows=audit(raw)
    answers={r['truth']:r['upper'] for r in rows}
    assert len(rows)==208 and all(r['lower']==r['upper'] and r['upper'] is not None for r in rows)
    return answers,dict(cap=meta['cap'],states=meta['states'],wall_s=receipt['wall_s'],
                        peak_bytes=receipt['peak_working_bytes'],sha256=receipt['table_sha256'])


def validate_batch(root,answers,complete):
    log=(root/'solver.log').read_text()
    blocks=re.findall(r'(?ms)^CF_BEGIN_([0-9a-f]{4})\s*$\n(.*?)^CF_END_\1\s*$',log)
    seen=set()
    for t,chunk in blocks:
        assert t not in seen
        seen.add(t)
        w=simulate(chunk,4,int(t,16))
        assert w['activity']==answers[t]
        assert re.search(rf"FRONTIER lower={answers[t]} paid_wires={w['gates']-1} projected=1", chunk)
    if complete:
        receipt=read(root/'result.json')
        assert receipt['verified']==len(seen)==len(answers)
        assert receipt['log_sha256']==digest(root/'solver.log')
        return dict(count=len(seen),wall_s=receipt['wall_s'],peak_bytes=receipt['peak_bytes'],
                    including_scalar_audit_s=receipt['including_scalar_audit_s'])
    return dict(completed_verified=len(seen),last_complete=blocks[-1][0],
                last_started=re.findall(r'(?m)^CF_BEGIN_(\w+)',log)[-1])


def verify():
    folder=HERE/'evidence'
    runs={}
    answers=None
    for name in ('direct-662','residual-projected','residual-uniform','matched-direct','matched-projected'):
        outcome,runs[name]=check_library(folder/name)
        if answers is not None: assert outcome==answers
        answers=outcome
    author=validate_batch(folder/'author-fixed',answers,True)
    superseded=validate_batch(folder/'author-batch',answers,False)
    history=read(STUDY/'evidence/full-300/summary.json')['arms']['B']
    assert history['completed']==91
    finite=read(folder/'finite-audit.json')
    assert finite['checked_images']==12582912 and finite['partner_cells']==49062
    assert [r['verified'] for r in finite['bounds']]==[222]*4
    epfl=read(folder/'epfl-cut-check.json')['designs']
    transitions=read(folder/'stable-transitions.json')
    circuits=[]
    for r,t in zip(epfl,transitions,strict=True):
        assert r['benchmark']==t['design']
        area,act=r['arms']['area'],r['arms']['activity']
        for v in (area,act):
            assert 'Networks are equivalent' in v['cec']
            assert sum(x['copies'] for x in v['per_truth'].values())==r['essential_4lut']
            assert sum(x['copies']*x['activity'] for x in v['per_truth'].values())==v['charged_activity']
        circuits.append(dict(name=t['design'],luts=r['essential_4lut'],area_score=area['charged_activity'],
                    optimum_score=act['charged_activity'],area_gates=area['two_input_gates'],
                    optimum_gates=act['two_input_gates'],stable_change=t['relative_change']))
    return dict(essential=len(answers),baseline_completed=history['completed'],
                additional=len(answers)-history['completed'],max_optimum=max(answers.values()),
                final_two={t:answers[t] for t in ('1681','1698')},runs=runs,
                causal_time_ratio=runs['residual-uniform']['wall_s']/runs['residual-projected']['wall_s'],
                causal_state_ratio=runs['residual-uniform']['states']/runs['residual-projected']['states'],
                matched_time_ratio=runs['matched-direct']['wall_s']/runs['matched-projected']['wall_s'],
                matched_memory_ratio=runs['matched-direct']['peak_bytes']/runs['matched-projected']['peak_bytes'],
                author=author,superseded=superseded,circuits=circuits)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    report=json.dumps(verify(),indent=2)
    if args.out: args.out.write_text(report)
    print(report)
