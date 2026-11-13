# Isolate instruction proof reductions

The existing `rvw.riscv-abstraction/1` manifest now has two optional booleans:

| Setting | Default | Effect |
| --- | --- | --- |
| `pipeline_restriction` | true | Restrict the listed stage-valid signals to at most one active bit |
| `ram_abstraction` | true | Run the selected RAM abstraction and retain the declared words |

Existing manifests keep both reductions. Set `pipeline_restriction` to false
for a RAM-only experiment. Set `ram_abstraction` to false for a single-flight
experiment on the concrete RAM. At least one setting must be true. Use
`rvw formal riscv-proof` for the original model with neither reduction.
Single-flight engine results are under `native_portfolio`. RAM engine results
retain their existing round and `rtlil_retry` records. The report records both
selected booleans, the exact restriction, source identity, time limits and load.
Concrete retirement covers also retain timing and load.

Run one instruction at a time. The upstream instruction checker already
selects that instruction. Then try RAM only, single-flight only and their
combination. Keep the original result. To make a helper assumption, first
prove the helper against the original transition system. Generated invariant
templates are candidates, not permission to assume the target. Try another
engine or solver option only with the same model and assumptions. Do not
change several reductions and attribute the gain to one of them.

## Short loaded-host diagnostic

On 2026-11-13, LUI used the VexRiscv FormalSimple RV32IC snapshot. Its RTL
hash matches the earlier instruction campaign. The current project wrapper
constrains instruction and data bus errors to zero. PDR and Bitwuzla raced
with a 15-second limit per engine. Checks ran in sequence at nice priority 5
under the private `vex-formal2` lock. The RAM phase had a separate 45-second
budget. Concrete retirement cover had a 15-second limit.

| LUI model | Native engine results | General retirement cover | One-minute load start / end |
| --- | --- | --- | --- |
| Original per-instruction checker | PDR timeout 15.103 s; Bitwuzla timeout 15.293 s | Not run in this command | 151.57 / 147.75 at engine execution |
| RAM only, word zero retained | PDR timeout 15.185 s; Bitwuzla timeout 15.207 s | Reached in 7.733 s | 146.31 / 137.01 for the check and cover |
| Single-flight only, concrete RAM | PDR timeout 15.317 s; Bitwuzla timeout 15.355 s | Reached in 9.409 s | 141.49 / 141.93 for the check and cover |

No unbounded instruction proof closed in this diagnostic. No smallest closing
change or real capacity limit was established. Covers establish general
retirement reachability, not activation of LUI. RAM word abstraction is an
overapproximation. The single-flight restriction omits fetch queues and is
not a proved invariant. Source reset and bus assumptions remain. Helper
invariants were not added or assumed in these runs. The combined model's
older timeouts remain historical results with no recorded per-check load.

Regenerate these attempts with native tools on PATH and a private
`RISCV_FORMAL` source copy. Keep output outside the repository:

```sh
scripts/with-lock.sh vex-formal2 nice -n 5 rvw formal riscv-proof \
  --project examples/vexriscv/formal \
  --checks insn_lui_ch0 --engines abc:pdr,smtbmc:bitwuzla \
  --timeout 15 --out "$RUN_ROOT/lui-original"
python3 - <<'PY'
import json, os
from pathlib import Path
plan=json.loads(Path('examples/vexriscv/formal/abstract.json').read_text())
for name,pipeline,memory in [('ram-only',False,True),('single-flight-only',True,False)]:
    selected=dict(plan,pipeline_restriction=pipeline,ram_abstraction=memory)
    (Path(os.environ['RUN_ROOT'])/(name+'.json')).write_text(json.dumps(selected))
PY
for mode in ram-only single-flight-only; do
  scripts/with-lock.sh vex-formal2 nice -n 5 rvw formal riscv-abstract \
    --project examples/vexriscv/formal --manifest "$RUN_ROOT/$mode.json" \
    --checks insn_lui_ch0 --engines abc:pdr,smtbmc:bitwuzla \
    --timeout 15 --budget 45 --out "$RUN_ROOT/lui-$mode"
done
```

Use a private lock and nice priority 5 for the original checker too. These
commands are diagnostics. Use the retained timeout replay at 30 minutes on
an idle machine before selecting capacity-based defaults.
