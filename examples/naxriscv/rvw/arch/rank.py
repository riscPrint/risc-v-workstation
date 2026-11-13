#!/usr/bin/env python3
"""Compare absolute RTL elasticity with the model sensitivity order, including ties."""
import json
from math import sqrt
from pathlib import Path
import sys


def agreement(sensitivity, matrix):
    model = {r["parameter"]: r["sensitivity"] for r in sensitivity["ranking"]}
    groups = {}
    for row in matrix:
        groups.setdefault(row["variant"], []).append(row)
    base = groups.pop("base")
    base_cycles = sum(r["cycles"] for r in base)
    rows = []
    for variant, samples in groups.items():
        changes = samples[0]["changes"]
        field, value = next(iter(changes.items()))
        baseline = next(r["baseline_value"] for r in sensitivity["ranking"] if r["parameter"] == field)
        change = base_cycles/sum(r["cycles"] for r in samples)-1
        rows.append(dict(variant=variant, parameter=field, measured_ipc_change=change,
                         measured_elasticity=abs(change/(value/baseline-1)),
                         model_sensitivity=model[field]))
    concordant = discordant = model_ties = rtl_ties = 0
    for i, a in enumerate(rows):
        for b in rows[i+1:]:
            x = a["model_sensitivity"]-b["model_sensitivity"]
            y = a["measured_elasticity"]-b["measured_elasticity"]
            concordant += x*y > 0
            discordant += x*y < 0
            model_ties += x == 0 and y != 0
            rtl_ties += y == 0 and x != 0
    denominator = sqrt((concordant+discordant+model_ties)*(concordant+discordant+rtl_ties))
    return dict(schema="rvw.nax-sensitivity-rank/1", fraction=sensitivity.get("fraction"),
                config_sha256=sensitivity.get("config_sha256"), rows=rows, concordant=concordant, discordant=discordant,
                model_ties=model_ties, rtl_ties=rtl_ties,
                kendall_tau_b=(concordant-discordant)/denominator if denominator else None,
                method="instruction-pooled RTL IPC; absolute elasticity; local model sensitivity",
                limits=["RTL steps differ from local model steps", "six whole-program samples; no uncertainty estimate"])


if __name__ == "__main__":
    print(json.dumps(agreement(*(json.loads(Path(p).read_text()) for p in sys.argv[1:])), indent=2))
