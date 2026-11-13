# BOOM daily-loop check, 2026-11-13

## Scope and source

This check uses workstation commit `163255125b1a313b6895c0f696e7c175a6de7d13`
from `origin/main`. BOOM uses private clone commit
`0cb0b694413c6eba5837560536cde80dad62ca00`. No core RTL was changed.
Only the `small` preset was used. Every simulation and native build used
`scripts/with-lock.sh boom nice -n 10`. The initial doctor adapter probe
used the adapter's own BOOM and sbt locks. The final doctor uses the outer
BOOM lock and `nice` too.

The private clone has one pre-existing tracked change: `env.sh` selects
Temurin 21.0.13 instead of the old JDK. This change was preserved. The
standalone run, quick tier and database record that dirty source state.
The gate explicitly selects the same committed BOOM revision on both sides.

Set `RVW_HOME` to this workstation checkout. Set `SPINAL_BOOM` to the
private clone. Set `RISCV_TESTS` to the built ISA directory under the
reference riscv-tests checkout. Set `VM_TESTS` to
`$SPINAL_BOOM/tests/vm/build`. Source the private clone's `env.sh`.
Add `rvw/.venv/bin` and the RISC-V GCC bin directory to `PATH`.
The commands below use `RUN_ROOT=examples/boom/out/boom-check-20261113`.
Evidence was moved there after the suite runs. This directory is ignored.

## Results

| Check | Recorded baseline | This run |
|---|---|---|
| Single add simulation | Daily-loop smoke | Pass; 2,479 cycles, 512 non-trapping retirements |
| Single add Spike comparison | Match | Match; 514 instructions and two trap events; complete C2/2 trace |
| Quick tier | ROADMAP.md: 173/173 | 173 pass, 1 fail, 0 inconclusive; 174 selected; 264.10 s wall time |
| ISA part of quick tier | Included in quick tier | 172 pass, 1 fail; 173 selected |
| VM part of quick tier | Included in quick tier | `ae_ptw`: 1 pass |
| Spike over quick-tier traces | ROADMAP.md: 173/174 | 173 match, 1 mismatch, 0 errors or inconclusive; 174 unique complete traces |
| Committed unchanged gate | Accept with known failure still failing | Accept; 174 compared, 0 new failures, 0 inconclusive; 605.83 s including lock wait |
| Failure bundle | Failure diagnosis | Pass; summary, last retired instructions and captured replay script |
| Design database | Build and query | Pass; 218 components, 128,226 signals, 53 memories |
| SpinalChecks | Elaboration | Compile and small elaboration pass; 519 checks inserted, 101 existing waived/disabled |

The quick tier used the default persistent worker path. Adapter logs contain
`run-many --jobs 1 --persistent` for each worker. One worker built the model;
the other three ISA workers and the VM worker reported Verilator cache hits.
Native cache identity checks were left enabled. The per-process fallback
was not needed.

The only simulation failure is `rv64mi-p-instret_overflow`:
`tohost = 0x5 (test 2 failed)`, fail code 2, at cycle 870 with 102 retirements.
Spike reports its first difference at order 82: `rd_wdata` is `0x1` on BOOM
and `0x0` on Spike. This is the known core bug from the task baseline.
It was neither masked nor waived.

The current quick plan selects 173 ISA programs, including this failure,
and one VM program. Its 173 passing programs must not be reported as
173/173 selected programs. The dated roadmap count has no test manifest
attached here. This check does not claim that its exact selection matches
the old selection. The current count and the known failure are explicit.

## Commands

```sh
rvw doctor --project examples/boom --features sim,riscv-gcc,cosim --json
nice -n 10 Cosim/build.sh
scripts/with-lock.sh boom nice -n 10 RiscvSim/boom/run.sh run \
  --elf "$RISCV_TESTS/rv64ui-p-add" --config small \
  --out "$RUN_ROOT/add" --rvfi-trace --json
rvw cosim doctor --core boom --trace "$RUN_ROOT/add/rvfi.jsonl" --json
rvw cosim check --core boom \
  --platform rvw/src/rvw/cosim/configs/boom.json \
  --trace "$RUN_ROOT/add/rvfi.jsonl" \
  --elf "$RISCV_TESTS/rv64ui-p-add" --json
scripts/with-lock.sh boom nice -n 10 rvw regress run \
  --core boom --tier quick --rvfi-trace --out "$RUN_ROOT/quick" --json
```

Each quick-tier trace is checked separately with the same BOOM platform:

```sh
rvw cosim check --core boom \
  --platform rvw/src/rvw/cosim/configs/boom.json \
  --trace "$TRACE" --elf "$ELF" --json
export RVW_RESULTS="$RUN_ROOT/gate-results"
scripts/with-lock.sh boom nice -n 10 rvw regress gate --core boom \
  --tier quick --base-rev 0cb0b694413c6eba5837560536cde80dad62ca00 \
  --cand-rev 0cb0b694413c6eba5837560536cde80dad62ca00 \
  --rvfi-trace --out "$RUN_ROOT/gate" --json
scripts/with-lock.sh boom nice -n 10 rvw bundle \
  "$RUN_ROOT/quick/riscv-tests/small/tests/rv64mi-p-instret_overflow" \
  --out "$RUN_ROOT/bundle-retry" --no-rerun --json
scripts/with-lock.sh boom nice -n 10 rvw query build \
  --project examples/boom --config small --out "$RUN_ROOT/boom.db" --json
rvw query info --db "$RUN_ROOT/boom.db" --json
rvw query search trace --db "$RUN_ROOT/boom.db" --limit 5 --json
rvw query hierarchy --db "$RUN_ROOT/boom.db" --depth 1 --json
rvw query drivers io_trace_insns_0_valid --db "$RUN_ROOT/boom.db" --json
rvw query where io_trace_insns_0_valid --db "$RUN_ROOT/boom.db" --json
scripts/with-lock.sh boom nice -n 10 bash -c \
  'cd SpinalChecks/boom && sbt -J-Xmx4g -batch compile \
  "runMain spinalchecks.boom.BoomChecks elaborate small ../../examples/boom/out/boom-check-20261113/checks"'
```

Database navigation returns the retirement-valid signal, its assignments,
its Spinal source location and its generated Verilog location. Navigation
prints a source-state warning because the clone's `env.sh` is dirty.

## Setup repairs and regression attribution

Initial doctor found a stale local Spike shim manifest and no generated
workstation `env.sh` in this worktree. Rebuilding the shim with the current
source and adding an ignored local environment file repaired these setup
inputs. These are local setup repairs, not generic-code fixes. No comparison
policy or platform mask was changed.

The first bundle attempt refused to capture the checkout because this check
put large evidence files under unignored `out/`. Moving this check
into ignored `examples/boom/out/` let the unchanged bundle command pass.
Its source capture limit was not changed. The bundle contains the failure
summary, last retired instructions and captured replay script. No wave or
SpinalTrace dependency graph was available. The replay script was not run.

An initial attempt to inspect the historical add trace used a path absent
from this checkout. The required doctor inspection was then run on the
fresh add trace. An exploratory `rvw query find` command was rejected;
the supported `rvw query search` command passed.

No new generic-code regression was found in the completed simulation, Spike,
gate, query or elaboration checks. Thus no causing merged PR or generic-code
fix is claimed for those checks. No feature code was added.

Final doctor reports native tools, adapter info, ISA discovery, VM discovery
and gate inputs ready. Its overall result remains `not_ready`: ACT4,
benchmark, stress and MMU suite inputs are absent; build-only elaboration
has no ELF inputs; the live source trees are dirty. Its own build/run probe
is inconclusive because `--smoke-elf` was not requested. Separate native
runs above provide execution evidence. Doctor is not an all-suite pass.

The fast Python set passed: 2,981 passed, 1 skipped and 8,081 deselected
in 149.50 seconds. Release hygiene passed all 40 tests. `rvw mcp --list`
completed with no `skipped` line on stderr. The full Python suite was not run.

The comparison driver encountered both the published suite paths and their
generation paths. It completed all 174 unique programs, then began duplicate
comparisons. The driver was stopped. Counts above use the first result for
each unique program, not duplicate paths. No unique test was skipped.

## Limits

NOT RUN: medium, large, mega and giga presets; ACT4; formal proofs;
SpinalChecks simulation; scheduled interrupts; fault injection; probes;
checkpoint/restore; device plugins; wave capture; Sail comparison.
The failure bundle uses the captured RVFI trace without a wave rerun.
These results qualify the tested small-preset daily loop only.
