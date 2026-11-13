# Custom instruction effect contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).
The pure version-1 interface remains documented in
[VexiiRiscv integration contracts](vexii.md#custom-r-type-instruction-interface).

## Extra-state, memory and trap transitions

`rvw.custom-isa/2` retains semantic version, XLEN 32/64, custom R-type encodings
and operands. Top-level `state` maps extra-state names to widths up to XLEN.
Every instruction declares `result`, `pc_after`, `state_updates`, `memory` and
`trap`. Memory is null or one load/store with byte size, address and store data.
A memory instruction requires explicit fault-trap semantics. Trap data supplies
`when`, `cause`, `target`, `state_updates` and, for memory, `memory_fault_cause`.

Word expressions use the version-1 unsigned operations plus pre-state, PC and
load-data operands. Trap predicates use eq/ne/ult/slt/all/any/not. Trap predicates
run before memory access and cannot read response data. Normal updates read
pre-state and commit together. Traps suppress normal destination/state commits
and apply only the declared trap updates. Trap updates can read `trap_cause`.
A memory fault without an attempted access is an error and an RTL assertion.
x0 suppresses the destination write but preserves other declared effects.

`rvw.custom-effects-plan/1` stores generated boundary, destination-alias and
fault stimuli plus project reference vectors. Generated expectations share the
model. Project hooks must initialize and observe extra state. No DUT execution
is implied. `rvw.custom-effects-generation/1` records source/generator/output
hashes, reference comparisons, effect mutants and missing evidence. A mismatch
exits 1. Generated artifacts exit 0. Invalid declarations exit 2. These are
transition models, not a bus handshake, AMO, compiler integration or ISA proof.
