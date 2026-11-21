"""Build the independent candidate and a sibling unmodified TCJAP control."""
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT / "tools"))
from build_variant import build


def lf_patch(source):
    dest = ROOT / ".local/orbit-patches" / source.name
    dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(source.read_bytes().replace(b"\r\n",b"\n"))
    return dest

if __name__ == "__main__":
    common = [lf_patch(ROOT / "variants" / (name+".patch")) for name in ("compositions","support","joint-trail")]
    trail = lf_patch(ROOT / "variants/sat-trail.patch")
    build("orbit-control",common,trail)
    directory = ROOT / ".local/variants/orbit-signed"
    directory.mkdir(exist_ok=True)
    shutil.copyfile(HERE / "orbit_filter.h",directory / "orbit_filter.h")
    build("orbit-signed",common+[lf_patch(HERE / "orbit.patch")],trail)
