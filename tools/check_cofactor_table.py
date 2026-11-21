"""Verify the exact three-input source data behind the solver's compiled lookup."""
import re
from probe_cofactor_cost import ROOT, exact_three_input_costs

src = (ROOT / "tools/cofactor_filter.h").read_text()
table = src.split("cone_opt_three[128] = {", 1)[1].split("};", 1)[0]
values = [int(i) for i in re.findall(r"\d+", table)]
assert len(values) == 128
for truth, optimum in exact_three_input_costs().items():
    assert values[min(truth, 255 - truth)] == optimum, (truth, optimum)
print("Verified all 256 raw three-input truth tables.")
