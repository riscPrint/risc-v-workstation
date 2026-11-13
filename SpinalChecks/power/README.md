# Sampled power intent checks

Run `rvw formal power --intent intent.json --out generated`.
MCP: `formal_power`. Add `--db design.db` to resolve declared DFT paths.
Use the emitted modules in a project wrapper with the DUT, then run the existing
formal flows. Generation does not run a solver. No hardware binding is inferred.

`rvw.power-intent/1` requires `event_model=always_on_sampled`. All monitors use
an always-on observation clock. Sample controls in their declared source phase.
Do not connect the monitor clock to a clock that can stop. The first active sample
must follow reset. The supply monitor requires the declared initial state after
reset. `states` insertion order defines the numeric `supply_state` encoding.
State names, supply availability, isolation values and legal transitions are
project choices. Unsupported intent keys are errors. UPF import is not supported.

Each domain declares `name`, `width`, `wake_bound`, `checks`, `states`, `initial`
and `transitions`. `width` is the monitored retained/output data width. Each
state declares boolean `power_good` and `isolated`. Self-transitions are legal.
The `checks` list selects the following modules in `power.sv`:

- `clock_gate`: changes of enable require `source_low`. A closed gate cannot
  emit a sampled edge or retain outstanding work. Wakeup requires an enabled
  edge within `wake_bound` observation samples. This model requires work to
  drain before stopping. It does not model pause/resume of outstanding work.
- `isolation`: isolation clamps the observed value. Isolation must precede loss
  of supply by one sample. Off-state raw validity must be false. A consumer can
  use a value only when it is valid or isolated. Internal off-state storage is
  unconstrained. Connect an independent validity observation.
- `retention`: save captures declared state while powered. Power-off requires
  a prior save. Restore requires power and a previous power-off. The next sample
  must match the saved state. Functional use requires power and completed restore.
  Reset cancels saved state and the restore obligation. Save and restore cannot
  coincide. Interrupted sequences must obey the same rules.
- `test_isolation`: functional mode blocks scan/test enables and clamps test
  outputs. Test accesses and protected writes require authorization, supply,
  and non-functional mode. Reset disables these checks. This is an explicit
  project policy, not a production security certification.

DFT entries declare `signal`, `role`, `controllability`, and `observability`.
Roles are `test_clock`, `test_reset`, `scan_mode`, `test_enable`, and `access`.
The last two fields record project constraints as text. Optional SpinalDB
resolution adds the RTL path, width and clock role, or an unresolved reason.
This inventories declared paths only. It does not discover all test paths or
measure controllability, observability, ATPG results, or scan coverage.

## Decisions

Separate retention from isolation. Keep off-state storage unconstrained.
State the sampled event model and reset policy. Keep physical glitch, supply
ramp, analog unknown, UPF, real-core binding and production DFT claims open.
