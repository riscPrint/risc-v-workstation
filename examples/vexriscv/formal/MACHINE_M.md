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

## MRET decision and directed reproduction

The saved SBY `trace_tb.v` was replayed with Icarus on the captured RTL.
The two returns reproduced MPP values 3 then 0, with privilege fixed at 3.
The replay reported the same privilege assertion failure at time 155000 ps.
For Icarus, the replay renamed the SystemVerilog keyword `event`, removed the
formal-only reset assumption and cover, and removed the generated initialization
of `_zz_rvfi_rs1_addr_1`. That name is a combinational alias in the original RTL.
The replay retained all other witness initial values and input stimulus.
It is witness simulation with selected initial state, not a from-reset program.

The independent from-reset program is [mret-mpp.S](findings/mret-mpp.S).
It sets MEPC, executes one MRET and reads MSTATUS. The native Icarus harness
is [mret-mpp-tb.sv](findings/mret-mpp-tb.sv). It uses an ordered one-cycle
instruction response and no interrupts or bus errors. It records the MPP field
in memory before writing `tohost`. It reads the linked program from
`program.hex`, indexed in 32-bit words relative to `0x80000000`.

| Observation | Captured VexRiscv RV32IM | Spike with `--priv=m` |
| --- | --- | --- |
| MSTATUS read after one MRET | `0x00000080` | `0x00001880` |
| Extracted MPP | 0 | 3 |
| Store to `observed_mpp`, `0x80001050` | 0 | 3 |

The short native runs completed on 2026-11-13. See the adjacent VexRiscv and
Spike logs. The core pin and RTL hash above apply. Spike identified itself as
1.1.1-dev. Both tools ran the same ELF, built with RV32IM_Zicsr and ILP32.
Spike used `-m0x7ffff000:0x200000 --isa=rv32im_zicsr --priv=m -l
--log-commits`. The memory region includes the ELF header segment.

Decision: the failure reveals a real MPP update deviation in this machine-only
configuration. It is not a pending-interrupt redirect or unconstrained-bus
artifact. The controller assigns MPP=0 unconditionally on MRET. It separately
fixes privilege at 3 when no lower mode is generated. Thus the second-return
privilege failure is downstream of the invalid MPP update on the first return.
The [privileged ISA](https://docs.riscv.org/reference/isa/priv/machine.html)
requires xPP to become the least privileged supported mode after xRET.
That mode is M here. Source CSR writes also reject unsupported MPP values.

The kit now observes MPP after return. The binding declares
`least_privileged_mode: 3`. The property retains the privilege assertion and
adds the MPP assertion. It does not waive this deviation or constrain away the
return. No upstream source was changed. The minimal core fix is to set MPP to
3 on MRET when U-mode is absent, and to 0 when U-mode is present. Other core
profiles are not qualified by this finding.

To rebuild the ELF, use `riscv64-unknown-elf-gcc -march=rv32im_zicsr
-mabi=ilp32 -nostdlib -Wl,-Ttext=0x80000000 -Wl,--no-relax mret-mpp.S -o
mret.elf`. Export with `objcopy -O verilog --verilog-data-width=4`.
Subtract `0x20000000` from the hex address records for the harness RAM index.
Compile the unchanged measured RTL and the harness with Icarus `-g2012 -s tb`.
The harness stops on the `tohost` write and fails on timeout. Its log is an
observation, not an automatic ISA verdict.

The updated native checks used the same RTL, depth 25 and a 150-second task
limit. Exception and interrupt entry again returned PASS with reached covers.
MRET returned FAIL with a reached cover. The added MPP assertion fails on the
first return, before the earlier second-return privilege failure.
Private evidence is `mret-fixed` in this worktree's local run directory.
