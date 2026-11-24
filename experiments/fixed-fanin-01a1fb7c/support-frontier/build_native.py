"""Add generated theorem certificates to the frozen TCJAP integration."""
from pathlib import Path
import sys
from synthesize import solution, native_row

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(HERE.parent))
from build_variant import build
from native_audit import spec


def main():
    name="fixed-fanin-pareto"
    dest=ROOT/".local/variants"/name
    dest.mkdir(parents=True,exist_ok=True)
    entries=[]
    for t in range(0,65536,2):
        answer=solution(4,t)
        if answer:
            row=native_row(4,t,answer["endpoints"][-1])
            entries.append('    {%d,"%s"},' % (t,spec(row)))
    assert len(entries)==208
    (dest/"pareto_table.h").write_text(
        "static const struct { unsigned truth; const char *spec; } pareto_entries[] = {\n"+
        "\n".join(entries)+"\n};\n")
    verify=(HERE.parent/"native_library.h").read_text()
    assert verify.count("PexaManFree(*original);")==1
    (dest/"pareto_verify.h").write_text(
        verify.replace("PexaManFree(*original);","if (*original) PexaManFree(*original);"))
    (dest/"joint_trail.h").write_text((ROOT/"tools/joint_trail.h").read_text()+
                                      "\n"+(HERE/"native.h").read_text())
    patches=[]
    for path in [*(ROOT/"variants"/(stem+".patch") for stem in
                   ("compositions","support","joint-trail")),HERE/"native.patch",
                 ROOT/"variants/sat-trail.patch"]:
        target=dest/path.name
        target.write_bytes(path.read_bytes().replace(b"\r\n",b"\n"))
        patches.append(target)
    build(name,patches[:-1],patches[-1])


if __name__=="__main__":
    main()
