# RV32IM controller transition checks

`machine_m.py` captures the measured `FormalMTop.scala` export. It adds
project observations to the copy. It does not edit VexRiscv source. It rejects
an RTL export with another SHA-256. See [the build record](SAIL_M.md) for
source pins and the elaboration method.

RTL SHA-256:
`420f2d5bd0100a07ca48542d232c76e8048a4bb73e03757e51cd1aa664027a37`.

```sh
rvw/.venv/bin/python examples/vexriscv/formal/machine_m.py \
  --rtl BUILD/rtl/VexRiscv.v --out CAPTURE
rvw formal machine-checks --manifest CAPTURE/machine.json \
  --out RESULTS --run --timeout 120
```

Use the existing `machine-checks` CLI or MCP tool on the generated manifest.
Add `--run` to the helper to run up to three checks in parallel. Hold the
private `vex-conn` lock and use `nice -n 10` for native work.

The observations delay each controller event by one edge. They capture the
before-state, cause, PC and actual redirect at that edge. After-state comes
from the updated core registers. The interrupt event excludes the simultaneous
exception case because the controller gives that exception priority. The
binding adds no bus, interrupt, opcode or pipeline assumptions. The runner
asserts reset only in the initial state.

## Measured results

The native run on 2026-11-13 used Yosys, SymbiYosys and Bitwuzla. Each check
and cover task had a 120-second limit. Assertions used a cycle bound of 25.

| Rule | Assertion | Trigger cover |
| --- | --- | --- |
| Exception entry | bounded PASS | reached |
| Interrupt entry | bounded PASS | reached at step 15 |
| Machine return | FAIL at step 15 | reached at step 9 |

The return witness executes two MRET transitions. The first has captured MPP
3 and current privilege 3. It clears MPP to zero. At the second transition,
captured MPP is zero and current privilege remains 3. The generated return
rule requires current privilege to equal captured MPP. That assertion fails.
The PC and interrupt-enable assertions do not fail in this witness.

This is a failed bound controller property on the captured model. It needs
review of the machine-only profile, MPP handling and event alignment before
attribution to the core. No source fix, assumption that excludes the second
return, or property waiver was applied. The result remains failed.

The entry checks cover local controller state and its redirect payload. They
do not prove that the next retired PC follows the redirect. CSR instruction
read/write consistency, instruction-fetch pairing, killed-instruction history
and PC chaining across traps were NOT RUN on this profile. These results do
not establish complete-machine or unbounded ISA signoff.

Private evidence directory: `machine-m-transitions-v1`. It retains the source
copy, generated observations, manifests, check and cover logs, and the return
counterexample VCD. No core build was needed for this run.
