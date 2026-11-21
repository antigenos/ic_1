"""Build the literature's symmetric-variable ordering on the same TCJAP control."""
from build import HERE, ROOT, build, lf_patch
import shutil

if __name__=="__main__":
    dest=ROOT/".local/variants/orbit-order-control"
    dest.mkdir(exist_ok=True)
    shutil.copyfile(HERE/"ordered_inputs.h",dest/"ordered_inputs.h")
    common=[lf_patch(ROOT/"variants"/(s+".patch")) for s in ("compositions","support","joint-trail")]
    build("orbit-order-control",common+[lf_patch(HERE/"ordered.patch")],lf_patch(ROOT/"variants/sat-trail.patch"))
