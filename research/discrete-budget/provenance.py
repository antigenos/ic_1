"""Fingerprint the exact frozen object inventory and generated inputs used for these binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from build import ROOT,HERE,OUTER


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("base",type=Path)
    args=p.parse_args()
    base=args.base.resolve()
    abc=base/".local/abc"
    joint=base/".local/variants/joint"
    response=(joint/"objects.rsp").read_text().splitlines()
    objects={line.strip('"'):digest((abc/line.strip('"')).read_bytes()) for line in response}
    assert len(objects)==len(response)
    rows={}
    for d in sorted((HERE/".local").iterdir()):
        if not (d/"abc.exe").exists():
            continue
        rows[d.name]={f:digest((d/f).read_bytes()) for f in (
            "abc.exe","pexact.c","pexact.o","joint_trail.h","window_proof.h","screen_window_filter.h") if (d/f).exists()}
        replaced=[r for r in (d/"objects.rsp").read_text().splitlines() if r not in response]
        assert len(replaced)==1 and (abc/replaced[0].strip('"')).resolve()==(d/"pexact.o").resolve()
        assert len(response)==len((d/"objects.rsp").read_text().splitlines())
    shared={name:h for name,h in objects.items() if name!="../variants/joint/pexact.o"}
    print(json.dumps(dict(screen="ec412cf07b55fe462f47f144e8b317c2cdcdf29a",outer=OUTER,
        original_binary=digest((joint/"abc.exe").read_bytes()),original_pexact=digest((joint/"pexact.c").read_bytes()),
        common_objects=len(shared),common_object_names_and_hashes_sha256=digest(json.dumps(shared,sort_keys=True).encode()),
        gcc=subprocess.check_output(["gcc","-dumpfullversion"],text=True).strip(),builds=rows),indent=2))


if __name__=="__main__":
    main()
