# VexiiRiscv integration contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Sail Zicond result slice

`rvw.sail-zicond/1` records the pinned Sail source path, SHA-256 and commit,
compiler identity and library hashes, implementation options, source line
traceability and generated model hashes. Scope is RV32 enabled Zicond result
selection with a separately generated R-type RVFI shell. Disabled-extension
traps, CSR MISA, RV64 and full-machine state are excluded.
The riscv-formal runner can add project instruction models to its private base
ISA instruction list when each added model has an explicitly requested check.
C3 `source.formal_inputs.instruction_set_additions` records these names. This
adds checks; it does not redefine the base ISA or establish extension compliance.

## Custom R-type instruction interface

`rvw.custom-isa/1` declares a semantic version, XLEN 32/64 and instruction rows.
Each row supplies `name`, `mask`, `match`, `operands=[rd,rs1,rs2]`, `state=[]`,
`effects={memory:none,trap:none,pc:next}` and a `result` bitvector expression.
Encodings use the four custom opcode spaces and mask `0xfe00707f`. Expressions
use operands, unsigned constants and binary add/sub/xor/and/or/sll/srl trees.
The evaluator and Verilog export wrap to XLEN and mask shift amounts.
`reference_vectors` supply rs1, rs2 and expected values. `mutants` supply an ID
and alternate result expression. Their independence remains an author obligation.

`rvw.custom-plan/1` records generated/reference vectors, dependency cases,
reference comparisons, detected/surviving mutants and gaps. No DUT execution
is implied. `rvw.custom-generation/1` records the input hash, checks, gaps,
toolchain/license scope and `generated` or `mismatch`. Generation exits 0;
a reference mismatch exits 1; malformed input exits 2. No result is a core
acceptance verdict. The GCC fragment and standalone decoder are integration
hooks. They are not installed compiler or disassembler plugins.

## VexRiscv bootstrap probe image

`rvw.vex-bootstrap-image/1` is project data for the bounded native probe.
`pc` is the unsigned decimal saved entry PC. `memory` is an ordered list of
`address` integers and hexadecimal `hex` bytes. Later rows overlay earlier
rows. The complete declared Spike RAM image comes first. The reset trampoline
and reserved bootstrap code follow it. This is not `rvw.arch-checkpoint/1`.
The producer owns the reserved regions and must exclude them from live data.

## VexRiscv reverse process port

The project process port wraps `rvw.vex-bridge-probe/1` bytes in the existing
`rvw.native-checkpoint/1` envelope. State inventories explicitly declare no
RNG, devices or active interrupts. RAM, pending bus requests and C2 state are
inside the native payload. Counters include retired instructions. The stopped
port owns immutable bytes; replay installs them in a new native process before
advancement. This port does not implement C1 resume publication.

## Live bridge synchronous memory state

The `rvw.spinal-state/1` inventory includes synchronous memory-read buffers.
The bridge lowers full-width read-first or don't-care synchronous ports to
explicit registers before it collects state. Their layout and payload use
the existing register arrays. Mixed-width and combined synchronous read/write
ports are refused. This changes native RTL identity. Older snapshots cannot
restore into the new layout. The caller still owns all bus response and input
state and must restore at a stopped low clock boundary.
