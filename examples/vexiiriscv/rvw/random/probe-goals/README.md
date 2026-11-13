# Native probe goals

The four ISA programs passed C1 and complete strict Spike comparison.
`plan.json` binds the exact generated RTL used by the source coverage sample.
Its bins count both branch-probe outcomes and data read/write offers.
Bus offers can be speculative. Signal wiring remains a project obligation.

The two temporal sequences use increasing cycles and bounded per-step gaps.
They do not correlate instruction IDs. The `add` and `beq` runs leave the
read/write sequence unhit. The `lw` and `sw` runs complete it. The reports
retain unhit goals and pending activations.

[The measurements](measurement.json) retain per-program counts and hashes.
`add.json`, `beq.json`, `lw.json`, and `sw.json` are the qualified probe reports.
Counts cover the full program, including setup and termination. No payload
attribution or C4 acceptance follows from these events.

[Retirement coverage](retirement-coverage.json) uses the independent C2 pair
observer. It hits 14 of 36 declared bins at distances 1, 2 and 4 on each core.
These are retirement-order observations. They do not measure pipeline stalls.
Paths in this saved report use display aliases. Raw traces remain in the
source coverage sample directory of the worker checkout.

Run `rvw cov probe-goals --result run/result.json --plan plan.json
--platform ../platform.json --json` with matching native artifacts. Use
`probe_plan` and event recipes in a campaign for UCB feedback. Keep probe
goals, semantic ISA bins, and retirement pairs as separate denominators.

## Native UCB controller sample

The [controller sample](controller.json) completed two attempts with seed base 71.
Both payloads earned their declared C2 sequence hit and complete strict Spike
qualification. Probe feedback observed 2 of 6 goals. Remaining
goals and pending activations stay visible. No gain over random is claimed.

`controller-settings.json` and `recipes.json` are portable templates. Measurements
used a private project copy with lock `vex-dv`. Set `RVW_SBT_LOCK=sbt-dv` for
private builds. Point the template at that private project for worker runs.
The native source capture and archived state retain the measured inputs. The
template paths differ from those sealed raw inputs. Raw state is under
`rvw/out/dv/probe-loop-v3-vexiiriscv` in the worker checkout.

The first preflight found a missing C1 option receipt. It passed software but
earned no qualification or feedback credit. The generic C1 driver now records
selected model flags under `options`. Regression checks remain unchanged.

The controller uses `controller-plan.json`. Its RTL identity differs from
`plan.json`, which binds the earlier four-program sample. The first controller
plan was rejected for this mismatch and earned zero event feedback. The fresh
campaign uses the separately bound controller model. Counts from these two
model contexts are not combined.
