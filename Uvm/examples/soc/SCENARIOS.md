# SoC virtual sequences

`rvw.uvm.scenarios.SocScenarios` provides four bounded scenarios.
`Uvm/pyuvm/soc_sequences.py` wraps them as `SocVirtualSequence`.
`Uvm/base/rvw_soc_sequences.sv` provides the SV UVM equivalents.
Projects supply a backend that drives actual pins and returns scoreboard
results. The library does not infer device behavior from a map.

| Scenario | Required behavior |
|---|---|
| boot | Reset the design and agents. Wait for project completion and positive checks. |
| interrupt_storm | Choose seeded causes and gaps. Hold each IRQ until a checked matching event. Clear requests after each event. |
| bus_error | Enable injection. Execute a transfer. Require an observed error and positive checks. Disable injection. |
| reset_during_traffic | Start traffic. Confirm a pending transaction. Reset the design and models. Require an observed abort and reset-state checks. Stop traffic. |

The Python backend implements these async methods:

| Method | Result |
|---|---|
| `reset()` | Reset DUT, agents and expected models together. |
| `boot()` | `{'checks': N}` after checked project completion. |
| `wait_cycles(count)` | Wait actual design cycles. |
| `irq(mask)` | Drive the declared interrupt pins. |
| `wait_interrupt(cause)` | `{'checks': N, 'cause': cause}` from actual reference comparison. |
| `inject_bus_error(enable)` | Select or clear project error injection. |
| `transfer(request)` | `{'checks': N, 'error': bool}` from the observed response. |
| `start_traffic()` | Return a project task handle. |
| `traffic_pending(handle)` | Return whether a real transaction is pending. |
| `check_reset(handle)` | `{'checks': N, 'aborted': True}` after reset-state and abort checks. |
| `stop_traffic(handle)` | Stop and join the project's traffic task. |

`N` must be positive. An empty report cannot pass. The Python library uses
`finally` to clear IRQs, disable injection and stop traffic on errors or
cancellation. The project owns all watchdogs in its callbacks. A callback
must not return merely because a request pin changed.

Use `await SocScenarios(backend, seed=7).interrupt_storm([3, 7, 11], count=16)`
for direct Python use. For pyuvm, assign `backend` on the virtual sequencer,
then start `SocVirtualSequence('interrupt_storm', seed=7, causes=[3, 7, 11])`.
The calling test owns its run-phase objection.

For SV, derive from `rvw_soc_sequences::backend`. Assign the instance to
`rvw_soc_sequences::sequencer.project`. Start `scenario` on that sequencer.
Set `mode`, `allowed_irqs`, `count`, `max_gap`, `error_address` or
`reset_delay` as needed. The simulator seed selects SV random choices.
The SV tasks clear injection and requests before they check normal response
errors. Projects must handle fatal errors inside their backend tasks.

The connected Spinal bus-master example uses the boot scenario for actual
reset and two checked register-reset reads. Its native seed 1 and 7 tests
still check 9 APB transfers, 9 AXI-Lite transfers and 4 UART frames each.
This is peripheral bring-up. It has no CPU boot program.

Seven unit tests check sequencing, seeded IRQ choices, wrong causes,
missing errors, missing traffic and cleanup. The SV package passes native
Verilator 5.049 lint with the pinned UVM package. Lint is not SV runtime
qualification. Native SoC interrupt-storm, bus-error and mid-traffic-reset
backends remain project work. No CPU, IRQ or reset architecture claim
follows from a callback test.
