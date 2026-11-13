# Native agent benchmark measurements

| Scope | Recorded value |
|---|---|
| Date | 2026-11-13 |
| Native qualification tools | `47c1784d508261a85885d9dc388e21836cf4119b` |
| MCP workflow tools | `cfd444d2e0bc3b8961981632c72e1ddbce19c46e` |
| VexRiscv source | `baf7dc82f855eddaf5b0a20a6802c526f127e38a` |
| OoO Mini source | `4a8757808d344f6db4660ce2e08ae88465f6e27a`, default config |
| ISA source | riscv-tests `d7e86f701b929b5d801f8cda1a4871ab05f452bb` |
| Native limits | nice 15, two make jobs, one adapter worker, private locks, 10,000 cycles; adapter caps 110 s for Vex and 120 s for OoO |
| Qualification | Baseline passes and matches Spike; seed fails with an explicit strict Spike mismatch; reference repair passes and matches; controls pass |
| Agent-task limit | Native source/test qualification covers reproduction and repair checks. No source-localising agent repair is demonstrated. |
| Excluded claims | Agent reasoning, native external repairs, root-cause proof, C4 acceptance, whole-core qualification |

| Core / task | Named detector | Native qualification | First Spike difference: order, PC, instruction | Direct check firing: ID and first cycle |
|---|---|---|---|---|
| Vex / xor | `rv32ui-p-xor` | qualified | 73, `0x800001a4`, `xor     a4, a1, a2` | None recorded |
| Vex / or | `rv32ui-p-or` | qualified; complete C1 cycle limit | 73, `0x800001a4`, `or      a4, a1, a2` | None recorded |
| Vex / and | `rv32ui-p-and` | qualified | 73, `0x800001a4`, `and     a4, a1, a2` | None recorded |
| Vex / sub | `rv32ui-p-sub` | qualified | 77, `0x800001b4`, `sub     a4, a1, a2` | None recorded |
| Vex / sltu | `rv32ui-p-sltu` | qualified | 95, `0x800001fc`, `sltu    a4, a1, a2` | None recorded |
| Vex / slt | `rv32ui-p-slt` | qualified | 95, `0x800001fc`, `slt     a4, a1, a2` | None recorded |
| Vex / bge | `rv32ui-p-bge` | qualified | 71, `0x8000019c`, `bge     ra, sp, pc + 12` | None recorded |
| Vex / beq | `rv32ui-p-beq` | qualified; complete C1 cycle limit | 61, `0x80000164`, `beqz    t0, pc + 20` | None recorded |
| Vex / lb | `rv32ui-p-lb` | qualified | 72, `0x800001a0`, `lb      a4, 0(sp)` | None recorded |
| Vex / sra | `rv32ui-p-sra` | qualified | 77, `0x800001b4`, `sra     a4, a1, a2` | None recorded |
| OoO / wakeup-race | `rv32um-p-mul` | inconclusive | None; matching prefix | No firing |
| OoO / freelist-leak | `rv32ui-p-add` | inconclusive; control check also fires | None; matching prefix | freelist.conservation:rename at 7 |
| OoO / recovery-map | `rv32ui-p-beq` | qualified | 80, `0x800001c4`, `beq     ra, sp, pc - 4` | ooo.property:map_owned at 46, freelist.conservation:rename at 49 |
| OoO / store-age | `agent-store-age` | qualified | 9, `0x80000024`, `lw      s2, 0(s0)` | No firing |
| OoO / flush-valid | `rv32ui-p-beq` | qualified | 1, `0x80000050`, `li      ra, 0` | ooo.property:rob_count at 4, freelist.conservation:rename at 4 |
| OoO / operand-ready | `agent-operand-ready` | qualified | 4, `0x80000010`, `add     s1, zero, s0` | ooo.property:issue_operands at 6, execution.operands:issue at 6 |
| OoO / rename-source | `rv32ui-p-sub` | unqualified; control also fails | 61, `0x80000144`, `bltz    a0, pc + 24` | No firing |
| OoO / mul-wakeup | `rv32um-p-mul` | inconclusive | None; matching prefix | No firing |
| OoO / mul-flush | `agent-mul-flush` | qualified | 10, `0x80000030`, `li      a5, 15` | No firing |
| OoO / lsq-order | `rv32ui-p-lw` | inconclusive | None; matching prefix | No firing |

| Timing definition | Meaning |
|---|---|
| Adapter seconds | Includes Scala/model setup and all programs in that phase. Baselines are shared batches. Seed and repair batches contain the named test and control. |
| Spike seconds | Strict check for the named test only. The raw report also keeps control checks and C1 execution times. |
| B / S / R | Baseline / seeded / reference repair. These are observed wall times, without a performance claim. |

| Core / task | Adapter B / S / R, seconds | Spike B / S / R, seconds |
|---|---|---|
| Vex / xor | 34.03 / 21.50 / 19.68 | 2.46 / 3.39 / 2.52 |
| Vex / or | 34.03 / 38.73 / 32.70 | 2.43 / 4.81 / 5.66 |
| Vex / and | 34.03 / 39.09 / 27.99 | 2.54 / 3.61 / 4.69 |
| Vex / sub | 34.03 / 34.62 / 20.17 | 2.45 / 2.48 / 4.13 |
| Vex / sltu | 34.03 / 24.74 / 14.48 | 3.21 / 1.92 / 2.11 |
| Vex / slt | 34.03 / 31.57 / 34.49 | 2.84 / 4.49 / 3.79 |
| Vex / bge | 34.03 / 47.38 / 31.54 | 3.01 / 3.86 / 3.05 |
| Vex / beq | 34.03 / 36.55 / 23.13 | 3.04 / 2.42 / 2.17 |
| Vex / lb | 34.03 / 21.80 / 14.89 | 2.35 / 1.97 / 3.27 |
| Vex / sra | 34.03 / 24.45 / 21.59 | 2.13 / 2.62 / 2.44 |
| OoO / wakeup-race | 41.61 / 37.12 / 20.11 | 3.00 / 2.21 / 2.24 |
| OoO / freelist-leak | 41.61 / 37.51 / 21.65 | 2.84 / 2.53 / 2.38 |
| OoO / recovery-map | 41.61 / 35.41 / 19.75 | 2.90 / 2.70 / 3.65 |
| OoO / store-age | 17.55 / 20.22 / 13.14 | 1.87 / 1.90 / 1.80 |
| OoO / flush-valid | 41.61 / 36.81 / 14.28 | 2.90 / 2.41 / 3.22 |
| OoO / operand-ready | 17.55 / 21.29 / 14.80 | 1.69 / 2.81 / 2.59 |
| OoO / rename-source | 41.61 / 36.23 / 39.06 | 2.56 / 3.41 / 2.97 |
| OoO / mul-wakeup | 41.61 / 34.45 / 20.41 | 3.00 / 2.95 / 3.14 |
| OoO / mul-flush | 17.55 / 21.27 / 13.85 | 1.73 / 2.06 / 2.05 |
| OoO / lsq-order | 41.61 / 34.54 / 18.79 | 2.82 / 2.87 / 2.70 |

| Initial OoO detector gap | Checked directed replacement | Native result |
|---|---|---|
| `store-age`: ISA `lw` passes | Older MUL blocks retirement; SW precedes a forwarding LW | Qualified; first mismatch is LW at order 9 |
| `operand-ready`: ISA `add` passes | ADD consumes one ready source and one pending MUL source | Qualified; first mismatch is ADD at order 4; operand checks fire |
| `mul-flush`: ISA `div` passes | Wrong-path DIV survives a taken branch and overwrites a reused ROB slot | Qualified; first mismatch is ADDI at order 10 |
| `rvw regress plan` | All three generated programs meet the pinned RV32IM feature requirements | Selection result only; native results above establish detection |
| Remaining stalls | `wakeup-race`, `mul-wakeup`, `lsq-order`, `freelist-leak` reach the cycle limit with a complete matching prefix | No first divergent instruction. They remain inconclusive. A bounded stall is not promoted to a Spike mismatch. |
| Rename control | `rename-source` also breaks the tohost control store | Unqualified under the pack control rule |
| Hard task labels | Three directed replacements and four remaining bounded stalls | The stalls remain inconclusive |
| Baseline and reference monitors | All recorded baseline and reference runs had no check firings | Seed-only firing is reported separately from architectural qualification |

## Bounded external MCP reference client

| Core / task | Returned workflow steps | Exact line rank / candidates | Client seconds | Calls | DB setup seconds |
|---|---|---|---|---|---|
| Vex / xor | 5/5 | Absent / 2 | 19.17 | 11 | 11.84 |
| Vex / and | 5/5 | Absent / 2 | 41.33 | 12 | 11.88 |
| Vex / beq | 5/5 | Absent / 2 | 49.37 | 12 | 11.23 |
| Vex / bge | 5/5 | Absent / 2 | 38.13 | 12 | 16.48 |
| Vex / lb | 5/5 | Absent / 2 | 17.10 | 11 | 20.65 |
| Vex / or | 5/5 | Absent / 2 | 36.34 | 11 | 14.66 |
| Vex / slt | 5/5 | Absent / 2 | 40.50 | 12 | 18.99 |
| Vex / sltu | 5/5 | Absent / 2 | 37.27 | 12 | 16.99 |
| Vex / sra | 5/5 | Absent / 2 | 18.27 | 11 | 13.33 |
| Vex / sub | 5/5 | Absent / 2 | 41.72 | 12 | 22.43 |
| OoO / recovery-map | 3/5 | Absent / 2 | 23.62 | 10 | 13.60 |
| OoO / flush-valid | 5/5 | Absent / 4 | 21.81 | 11 | 19.96 |
| OoO / freelist-leak | 5/5 | Absent / 4 | 28.98 | 11 | 11.32 |
| OoO / lsq-order | 5/5 | Absent / 4 | 18.49 | 11 | 11.86 |
| OoO / mul-flush | 5/5 | Absent / 4 | 21.73 | 11 | 23.28 |
| OoO / mul-wakeup | 5/5 | Absent / 4 | 26.11 | 11 | 19.18 |
| OoO / operand-ready | 5/5 | Absent / 4 | 23.65 | 11 | 11.17 |
| OoO / rename-source | 5/5 | Absent / 3 | 17.47 | 11 | 18.56 |
| OoO / store-age | 5/5 | Absent / 4 | 17.98 | 11 | 14.24 |
| OoO / wakeup-race | 5/5 | Absent / 4 | 27.69 | 11 | 15.52 |
| OoO retry / recovery-map | 3/5 | Absent / 2 | 14.05 | 10 | 12.90 |

| Budget and score | Recorded value |
|---|---|
| Per attempt | 110 seconds and 32 calls, including status waits, wave-time search, inspect and finish |
| Complete five-step attempts | 19 / 21 |
| Exact mutated line returned | 0 / 21 |
| Claimed fixes / correct fixes / false fixes | 0 / 0 / 0 |
| Preparation | Mutant database creation is measured separately, outside the client budget |
| Recovery-map attempts | Bundle and wave search failed twice when `fst2vcd` exited with signal 11. Retained in the denominator. Cause is not established. |

## Native misleading evidence and independent repair

| Replayed actual native capture | MCP admission | Fix credit |
|---|---|---|
| control | evidence_consistent | 0 |
| stale-rtl | inconclusive | 0 |
| wrong-elf | inconclusive | 0 |
| unsupported-fields | inconclusive | 0 |
| missing-coverage | inconclusive | 0 |
| missing-end | inconclusive | 0 |

| Candidate RTL | Named XOR test | Hidden SUB test | Native scoring verdict |
|---|---|---|---|
| Seed | fail | pass | Reproduction |
| XOR repaired, SUB broken | pass | fail | unqualified; no fix credit |
| Reference repair | pass | pass | qualified |

| Interpretation | Evidence boundary |
|---|---|
| Architectural fault detection | Strict Spike gives a first wrong retirement for all 15 qualified tasks. It cannot give a first wrong instruction for a matching prefix that stops. |
| Direct OoO checks | Free-list conservation, map ownership, ROB count and operand readiness detect four seeded task classes. No baseline or reference run fired these checks. |
| Vex localisation limit | The observable RVFI output reaches its wrapper assignment. The next compiler temporary is absent from the wave. |
| OoO localisation limit | Register-bank write enables such as `(1 << selected)(slot)` have no wave signal binding. The explanation stops at an ambiguous write. |
| Rank scope | Exact mutated line among unique returned source locations, in traversal order. Null means absent. No nearby-line credit. No claim that another search strategy would also fail. |
| Tool workflow scope | Query the public architectural mismatch signal, then wave why at the live retirement order, depth 12 and at most 256 nodes. No oracle microarchitectural signal is supplied. |
| Database and wave binding | Source bytes are evaluator controlled, but the tool still labels the database/wave name join unverified. Returned locations are not causal proof. |
| External score | This MCP surface has no source-edit or independent repair-check tool. Correct fixes and false fixes are both zero because the client claims no fix. Root-cause times remain censored. |
| Misleading input scope | Five cases modify or omit evidence from one actual native capture. They are native-evidence replay cases, not five new simulations. |
| Independent wrong-fix scope | Actual candidate RTL passes XOR and fails the hidden SUB test. The existing native verdict rejects it. This checks the scoring predicate in a controlled private workspace. It does not qualify an untrusted external repair. |

## Regeneration

Run from the workstation root. Use private source checkouts at the pins above.
Keep raw output outside Git. Set `RUN_ROOT`, `VEX_SOURCE`, `OOO_SOURCE` and
`RISCV_TESTS` to private absolute paths. Each source is a clean original checkout.
Do not set a source variable to a qualification workspace.

```sh
source /path/to/spinal-boom/env.sh
export RVW_HOME="$PWD" RVW_VEX_LOCK=vex-agentbench RVW_OOO_LOCK=vex-agentbench
export RVW_SBT_LOCK=sbt-agentbench RVW_NICE=15 RISCVSIM_MAKE_JOBS=2
export JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2
export PATH="/opt/homebrew/opt/riscv-gnu-toolchain/bin:$PATH"
nice -n 15 rvw/.venv/bin/python examples/agent-bench/build-native-tests.py \
  --source "$RISCV_TESTS" --out examples/agent-bench/out/isa-control
nice -n 15 rvw/.venv/bin/python examples/ooo-mini/rvw/build-isa.py "$RISCV_TESTS"
cp examples/agent-bench/out/isa-control/agent-control examples/ooo-mini/rvw/out/isa/
nice -n 15 rvw/.venv/bin/python examples/agent-bench/build-hard-tests.py \
  --isa-dir examples/ooo-mini/rvw/out/isa --out "$RUN_ROOT/hard"
rvw/.venv/bin/rvw regress plan --features examples/ooo-mini/rvw/features.json \
  --catalog "$RUN_ROOT/hard/catalog.json" --json > "$RUN_ROOT/hard-plan.json"
nice -n 15 rvw/.venv/bin/rvw agent-bench native-qualify \
  --pack examples/agent-bench/native.json --source "$VEX_SOURCE" --out "$RUN_ROOT/vex"
nice -n 15 rvw/.venv/bin/rvw agent-bench native-qualify \
  --pack examples/agent-bench/ooo-mini.json --source "$OOO_SOURCE" --out "$RUN_ROOT/ooo"
nice -n 15 rvw/.venv/bin/rvw agent-bench native-qualify \
  --pack "$RUN_ROOT/hard/tasks.json" --source "$OOO_SOURCE" --out "$RUN_ROOT/ooo" \
  --reuse-workspace --task store-age --task operand-ready --task mul-flush
nice -n 15 rvw/.venv/bin/python examples/agent-bench/measure-native-tools.py \
  --core vexriscv --pack examples/agent-bench/native.json --source "$VEX_SOURCE" \
  --workspace "$RUN_ROOT/vex/workspace" --out "$RUN_ROOT/vex-tools"
nice -n 15 rvw/.venv/bin/python examples/agent-bench/measure-native-tools.py \
  --core ooo-mini --pack "$RUN_ROOT/hard/tasks.json" --source "$OOO_SOURCE" \
  --workspace "$RUN_ROOT/ooo/workspace" --out "$RUN_ROOT/ooo-tools"
nice -n 15 rvw/.venv/bin/python examples/agent-bench/check-wrong-fix.py \
  --source "$VEX_SOURCE" --workspace "$RUN_ROOT/vex/workspace" \
  --qualification "$RUN_ROOT/vex/qualification.json" --out "$RUN_ROOT/wrong-fix"
```

A bounded cold build can stop before simulation. Retry the same qualification
command with `--reuse-workspace`. Keep the source path fixed. Each retry reruns
all checks and archives the old report. A prior partial run earns no pass.
Build timing and ELF hashes can change between builds. Each run records its own
identities. The three directed source programs reproduce the tested instruction
and data images. No cross-build byte-identical ELF claim is made.


Use a baseline run path and its seeded task RTL hash from the retained Vex
qualification report to replay the misleading inputs through MCP:

```sh
nice -n 15 rvw/.venv/bin/python examples/agent-bench/audit-misleading.py --mcp \
  --run-dir "$BASELINE_RUN" --elf examples/agent-bench/out/isa-control/rv32ui-p-xor \
  --wrong-elf examples/agent-bench/out/isa-control/rv32ui-p-or \
  --stale-rtl "$SEEDED_RTL_SHA256" --out "$RUN_ROOT/misleading"
```
