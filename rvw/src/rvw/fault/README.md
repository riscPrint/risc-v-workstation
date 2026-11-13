# Fault injection campaigns

`rvw fault` runs fault injection campaigns for functional safety (#52). It selects
register sites from the design database, samples stuck-at and transient faults
with a seed, runs each fault through the core adapter, and classifies the result
against the golden C2 trace.

```sh
rvw fault sites --db build/design.db --include 'core.regfile.*'
rvw fault plan --db build/design.db --include 'core.*' --kinds stuck0,stuck1,flip \
  --window 100:5000 --samples 500 --seed 7 --out plan.json
rvw fault run --plan plan.json --adapter './adapter.sh' --elf test.elf --out /tmp/faults \
  --jobs 4 --detections detections.json [--watchdog]
rvw fault report /tmp/faults
```

`rvw fault sites|plan --sites FILE` takes a site list (`{"sites": [{"path", "width"}]}`) in
place of `--db`, for example `rvw probes convert EVENTS --to fault-sites` from
`Probe.faultSite` probes. `--include`/`--exclude` still apply.

## Fault model

- Sites: design database `signals` with `kind = 'reg'`, not pruned. Generated
  registers only with `--generated`. Each bit of a register is one site bit.
- `stuck0`, `stuck1`: the bit holds from the start cycle, for `--duration` cycles or
  for the rest of the run. `flip`: a single-cycle upset at the start cycle.
- The population is site bits times window cycles for each kind. The plan records it.
  If the population is smaller than `--samples`, the plan is exhaustive.

## Adapter contract

The adapter receives `run --elf ELF --out DIR --rvfi-trace --fault FILE`. `FILE` is
`rvw.fault/1` JSON: `{"faults": [{"id", "kind", "site", "bit", "cycle", "duration"?}]}`.
It must write C1 `result.json` with `details.fault`: `{"applied": true, ...}` once the
bit was forced, or `{"applied": false, "reason": ...}`. Detection mechanisms that
fired go in `details.detections` (names). An adapter that does not confirm the
injection gives `not_injected` for every fault: injection success is measured
separately from detection. The generic RiscvSim driver implements `--fault` for
adapters that run through `SimSession` (see `RiscvSim/README.md`, "Fault injection").
The BOOM adapter runs through `SimSession`, but it is not tested with faults.

## Classification

| Class | Meaning |
|---|---|
| `detected` | The run failed (fail, assert, rvfi_error), a declared mechanism fired, or (with `--watchdog`) it timed out |
| `silent_corruption` | The run passed, but its architectural C2 records (pc, insn, rd, rd_wdata, memory writes, traps, mode) differ from the golden run |
| `safe` | The run passed with the golden architectural trace |
| `timeout` | The run did not end, and no watchdog is declared |
| `not_injected` | The adapter did not confirm the injection |
| `inconclusive` | Harness error, a missing trace, or an unknown status |

`--detections` is JSON: `{"mechanisms": ["parity_x9"], "status": {"fail": "self-test"}}`.
Only declared mechanism names count as detection.

The report (`report.json`, `rvw.fault-report/1`) gives counts, the population, the
sampled fraction, diagnostic coverage `detected / (detected + silent_corruption + timeout)`
with a 95 % Wilson interval, the safe fraction and the unresolved faults. The C3
file (`results.json`, suite `fault-campaign`) has one test per fault: `pass` for
detected or safe, `fail` for silent corruption, `error` (inconclusive) otherwise.
`outcomes.json` keeps every fault with its evidence.

## Limits

This is a simulation estimate over the sampled faults. It is not measured hardware
reliability. It makes no ISO 26262 compliance or tool qualification claim. FMEDA
assumptions, equivalence groups, protected-memory codewords, lockstep checks and
security fault campaigns from #52 are not implemented. Memories (`memories` table)
are not sites yet. Timing differences without architectural differences are safe.

## Decisions

- Classify against the golden C2 trace, not only the pass/fail status: a passing
  run with different architectural effects is silent corruption.
- The adapter forces the fault: the workstation never edits the core.
- Tests use a fake adapter that runs the debug model hart (`rvw/tests/fixtures/fault/adapter.py`).
