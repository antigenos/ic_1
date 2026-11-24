"""Read-only audit of the frozen archive; no solver processes are launched."""
from pathlib import Path
import argparse
import json
from datetime import datetime
from audit_results import DEV,TEST,examine,timing_summary,diagnostic_summary,read

def check(raw):
    count=0
    for part,cases in [('dev',DEV),('holdout',TEST)]:
        for kind in ['audit','timed']:
            data={}
            for t in cases:
                accepted=[]
                for path in raw.glob(f'{part}-{kind}-core-{t}-*'):
                    host=read(path/'host.json')
                    if host['returncode']==0 and not host['clashes']: accepted.append(path)
                assert len(accepted)==1,(t,kind,accepted)
                path=accepted[0]
                result=examine(path,[t],kind=='audit',full_order=cases)
                last_end=0
                for r in sorted((path/t).glob('*/result.json')):
                    row=read(r)
                    launch=read(r.parent/'launch.json')
                    req=read(r.parent/'request.json')
                    assert all(row[k]==v for k,v in req.items())
                    assert all(row[k]==v for k,v in launch.items())
                    assert row['capped_wall_s']==min(row['wall_s'],row['timeout_s'])
                    start=datetime.fromisoformat(row['start_utc']).timestamp()
                    assert start>=last_end-0.02
                    last_end=start+row['wall_s']
                    if kind=='audit':
                        lines=(r.parent/'solver.log').read_text().splitlines()
                        qs=[dict((k,int(v)) for k,v in (s.split('=') for s in l.split()[1:]))
                            for l in lines if l.startswith('QUERY ')]
                        assert qs==read(r.parent/'queries.json')
                    count+=1
                data.update(result)
            expected=read(raw/f'{part}-{kind}-summary.json')
            actual=(diagnostic_summary if kind=='audit' else timing_summary)(data)
            assert expected==actual
    print(f'Checked {count} accepted runs against raw logs and independent activity bounds.')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('raw',type=Path,nargs='?',default=Path(__file__).resolve().parent/'raw')
    check(p.parse_args().raw)
