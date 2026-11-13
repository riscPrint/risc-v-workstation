# Architectural injection API

`injection.plan` checks an `rvw.arch-injection/1` state document and a
`rvw.arch-map/1` project map. Both must name the same project profile. The map
lists `xlen`, `flen`, `pc`, 32 `gpr` signal names, zero or 32 `fpr` signal names,
and a `csr` map from hexadecimal addresses to signal names. Bind each signal
once. A profile must list the complete mutable CSR inventory of that core.
This API cannot infer that inventory from observed CSR accesses.

State includes integer `pc`, all 32 integer GPR values with x0=0, raw FPR
integers, and the exact CSR inventory. It includes `memory` rows with integer
`address` and hexadecimal byte string `hex`. Rows must not overlap. A producer
must provide the complete physical RAM image required by its profile. Missing
RAM does not imply zero fill. All values must fit their declared raw width.

The first executable profile supports `privilege: M`, `translation: bare`,
empty `devices` and empty `pending_interrupts`. `execution` declares one hart,
no pending trap, reservation, debug, WFI or external effects. Other execution
state is refused. FP injection preserves every raw FLEN bit, including f0 and
NaN boxing. This is an API capability, not qualified FP RTL transfer evidence.

`inject(port, state, mapping)` holds fetch, clears microarchitecture, writes
RAM and mapped registers, and reads every value back before fetch release.
The port supplies `hold_fetch`, `clear_microarchitecture`, `write_signal`,
`read_signal`, `write_memory`, `read_memory`, and `release_fetch`. Its clear
method must reset or flush hidden pipeline, cache and TLB state. Discard the
DUT after an error. Never release fetch after a failed readback.

`bootstrap_rv32` emits assembly for cores without injection hooks. Load memory
separately. Link the bootstrap at unused RAM within the direct JAL range of the
saved PC. The linker must reject a target outside that range. The program
writes supported machine CSRs, restores x1 through x31, then jumps without a
scratch register. It requires RV32IM, disabled interrupts and no FP. Bootstrap
execution changes cycle and instruction counters. It does not reproduce saved
microarchitecture. It cannot supply the injection path's pre-fetch readback.

This is not the qualified `rvw.arch-checkpoint/1` Spike interchange format.
Spike export/import, continuation comparison, full RAM inventory qualification,
VexRiscv hooks, C1 sample completion, and native FP, VM and device profiles
remain open. The assembler/linker smoke proves generated code links. It does
not prove that RTL restores architectural state.
