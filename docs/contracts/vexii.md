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

## VexiiRiscv supervisor C2 observations

The supervisor profiles write C2 `mem_addr` as the LSU virtual address that
the adapter samples when the native bus accepts the request. A micro-op tag
binds it to the probe's physical access. An AMO store half binds to the latest
hart command at its physical address. C1 `details.translated_addresses` lists
requests whose two addresses differ. C2 `tval` uses the core's CSR write
expression (`expendPc` to XLEN). C2 `mmu_walks` records come from the MMU
refill state machine: its start request, each PTE read on the walker port and
its refill response, which includes the walker's permission check. They follow
the ordered MMU walk observation contract in [mmu](mmu.md). C1 `details`
counts `mmu_walks` and `mmu_walks_unattached`. RiscvSim `RvfiRecord.extra`
appends such adapter-observed fields to one C2 line in order.

## Run-level strict reference check (`rvw.regress-cosim/1`)

`rvw regress cosim RUN_DIR --platform P` writes `schema`, `run`, `platform`,
`model`, `allow_sync`, `counts`, `suites` (counts per suite directory) and `rows`. Each row
has `suite`, `test`, `c1_status`, `cycles`, `instret` and `status`: `match`,
`mismatch` (with the first `mismatch`), `fail`, `error` or `inconclusive`
(with `reason`). `match` needs a passing C1 result and a complete
comparison whose masks and synchronizations all have reasons allowed by
`allow_sync` (`reset`: `csr_reset_unknown`; `irq`: `irq`; `mmio`: `mmio`). An empty
`allow_sync` means strict mode. Match rows record `synchronized`. The exit
code is 0 only when every row matches.

## Floating-point configurations

The extra `rv32imafc` and `rv64imafdc` machine configurations use the pinned
external core without source changes. Their project files are `rvw32fp.toml`
and `rvw64fp.toml`. Integer defaults are unchanged.

The FP adapter writes C2 version 2 with `state` and `csr` capabilities.
The upstream committed FP write supplies `fd_valid`, `fd` and `fd_wdata`.
This includes writes to `f0`. The 64-bit transport keeps NaN boxing for
single-precision values. RTL taps supply accrued `fflags`, `fcsr` including
`frm`, and a complete machine-only `mstatus` snapshot at `0x300`.
The native timing of these taps must pass strict comparison before the
configuration has qualification credit. No reference value fills a DUT field.

The upstream probe gives expanded compressed instructions. The adapter uses
the expanded fields for register effects and reads the raw encoding at the
retired PC for C2. A final non-control compressed instruction advances two
bytes. Intermediate next PCs come from the next observed retirement.

## Correlated FP state writes

The FP capture binds the real enabled flag, CSR and FS dirty write ports.
It registers each enable, value and micro-op ID on the edge that updates
storage. Decode allocation gives each reused hardware ID a new generation.
The generic `FpCommitState` checks actual fcsr and FS/SD storage against
those observed writes. A missing flag, missing dirty update, unexplained
state change or unretired effect stops capture. It never fills DUT data
from Spike.

Records use retirement order after all their state writes have settled.
FP destination data still comes directly from the upstream committed RF
probe. The accepted FCSR writes and observed raised flags supply accrued
flags and rounding state. FS/SD comes from the observed dirty requests and
actual status writes. Other mstatus bits retain the existing RTL capture,
including the later machine-return apply edge.

FP records are buffered for one bounded run. Streaming DPI is not bound.
Overlapping CSR and FP writes without separate physical snapshots stop
capture. Final projected state must equal final actual storage. These are
capture limits, not waived comparisons or core qualification.
