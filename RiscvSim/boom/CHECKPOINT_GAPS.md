# BOOM checkpoint and device gaps

This is a source review. BOOM checkpoint and restore are NOT RUN.
Do not use generic checkpoint support as evidence of a BOOM binding.

## Missing bindings

| State | Existing support | BOOM gap |
|---|---|---|
| Verilator context and RTL | `RiscvSim/src/main/cpp/Checkpoint.h` saves a context and model at a settled edge | The Scala adapter has no JNI save/restore binding. The current native model does not use `--savable`. |
| Backing memory | BOOM creates `SparseMemory` in `BoomAdapter.run` | Save and restore every backing page without reloading the ELF over restored data. |
| Pending memory work | `BoomMemoryAgent` uses the Spinal TileLink memory agent | Save pending requests, responses, latency and random state. Restore with no duplicate accepted transfer. |
| Devices and interrupts | Fixed CLINT and interrupt-generator registers use backing memory | Save register state, timer phase, current interrupt levels and schedule position. |
| C2 output | `RvfiTraceWriter.checkpoint()` and resume support exist | Bind the writer checkpoint to the exact stopped RTL edge and restored trace prefix. |
| Probe and run state | The adapter collects probes, cycles and retirement counts | Restore all counts and output positions with the native state. |
| Online reference | The C2 writer refuses lockstep resume without a reference checkpoint | No matched Spike/reference checkpoint is bound to BOOM restore. Keep the refusal. |

A save must include all these states in one identity-bound checkpoint.
A native RTL snapshot alone cannot restore this harness.
A restore failure must discard the instance.

## Device plugins

The adapter creates fixed `SparseMemory` and `BoomMemoryAgent` instances.
It does not dispatch through `LiveDevices`, `PluginDevice` or `DeviceDpi`.
Its map checks require the fixed CLINT and interrupt-generator registers,
interrupt routing and RTL address windows. A generic plugin example does
not establish a BOOM plugin binding.

A future binding must dispatch accepted MMIO transfers through the selected
device backend. It must preserve byte masks, access sizes, response errors
and deterministic device timing. The map must match the fixed RTL decode.
Plugin and device state must participate in checkpoint and restore.

## Build budget

The continuation reserved at most three native builds. The first exposed a
prediction-history binding error. The second retains the enqueue prediction.
The remaining build was reserved for probe and DPI integration failures.
This update adds no checkpoint RTL variant. It claims no restored run or
native plugin result. Refs: #6.
