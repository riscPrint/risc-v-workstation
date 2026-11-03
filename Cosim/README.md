# rvw cosim

Trace-driven architectural comparison for any scalar RISC-V core emitting the
[C2 trace contract](../docs/PLATFORM_CONTRACTS.md#c2-rvfi-trace-rvfijsonl).
This is the first implementation of an open replacement for the lockstep portion
of ImperasDV / Questa RISC-V VIP. It does not claim commercial feature parity.
Offline checking starts after simulation. The live integration API can check a
flushed retirement stream during simulation. Neither mode needs an RTL rebuild.
Generic code is in `rvw/src/rvw/cosim/`. BOOM's memory map is isolated in
`rvw/src/rvw/cosim/configs/boom.json`.

## Build and run

Install matching Spike headers and libraries, a C++20 compiler, and Python >=3.11.
The shim uses `processor_t`, `simif_t`, `state_t`, the MMU and disassembler from
Spike's public installed headers. It calls `processor_t::step(1)` per instruction,
uses commit effects, and edits reference integer registers after synchronization.
It neither drives Spike's interactive debugger nor compares post-hoc commit logs.

```sh
cd rvw
uv venv
uv pip install -e '.[dev]'
cd ..
Cosim/build.sh
rvw/.venv/bin/rvw cosim check --trace run/rvfi.jsonl --elf /path/test.elf --core boom --json
```

`SPIKE_PREFIX` defaults to `/opt/homebrew`; set it for another installation.
`CXX` selects the compiler. `RVW_SPIKE_SHIM` selects a separately built shim.
The default build goes under ignored `Cosim/build/`. Rebuild after changing the
installed Spike headers or library (a changed library hash is rejected): Spike's C++ ABI is not stable across versions.
A shim must also be the build of the current `Cosim/spike_shim.cc`. `build.sh` compiles the
source's sha256 into the library (`rvw_shim_source_sha256()`), and the library exports
`rvw_shim_version()`; the build manifest (`librvw_spike.so.manifest.json`) records both.
`rvw cosim` loads a shim only if the manifest exists, and the manifest and the library both
report the version the Python code expects (`SHIM_VERSION` in `rvw/src/rvw/cosim/spike.py`) and the
hash of the current source. Anything else (an old shim without the version, a shim built
from another source) is refused with exit 2 and "rebuild with Cosim/build.sh".
A missing input or manifest is inconclusive with exit 3. An old shim can change
results silently (before version 2 it cleared a
software-set SEIP). Change `SHIM_VERSION` and `rvw_shim_version()` together.
Use an editable installation from this repository; a standalone Python wheel does
not bundle the native library or build script.

Verified installation: Spike `1.1.1-dev`, Homebrew `riscv-isa-sim/main`, arm64.
The installer pins source builds to `eff659cd43d7eafb7f3559bceed2540eabb31c50`
(2025-08-11). The tested bottle's SBOM source timestamp matches that commit;
all 30 installed `riscv` headers present in that source tree match byte for byte.
The formula uses `version "main"` without a source revision, so the bottle's
exact source commit is inferred from this evidence, not attested by its receipt.
Homebrew tap receipt revision: `2434aac00803d570c1b04190c76f647e7d1661e7`.
Fresh `--with-cosim` installs build this pin on macOS and Linux. Existing matching
headers/libraries, including an explicit `SPIKE_PREFIX`, remain external inputs;
they are reused and identified by the build manifest. Do not use a moving
Homebrew formula as a portable source pin.

The later `5cf8c829d2033c5132158b59860fea8d6c06a94d` pin changes library defaults.
Upstream commit `1bf835816a6871a4b638d0795054bb726eec5d6c` starts
`processor_t` with `set_max_vaddr_bits(0)`. Spike's full simulator sets the MMU
from its device tree; this shim does not use that simulator. With that revision,
SUM/MXR read as zero and translated data/instruction accesses run without the
expected MMU. This explains the extra illegal, dirty and icache-alias differences.
It is not the later `cfg.misaligned` removal or a changed A/D policy.
Use the qualified pin with this shim. A newer Spike needs explicit MMU setup
before reset; building the shim alone does not qualify that reference.

Source installs record their version and revision in `share/rvw/spike-source.json`.
The build captures that file, or the Homebrew receipt and available SBOM, and puts
`spike_identity` in the manifest and its bound build inputs. External builds without
this metadata use null version/revision. Package metadata is a label supplied by the
installation. The actual library hashes remain authoritative. Every check
records the actual shim/library hashes and embedded shim version; no source-build fallback
was necessary. Sail `0.15` was also exercised.

Exit codes: **0** matching recorded execution, **1** first architectural mismatch,
**2** malformed captured data or unsupported reference execution,
**3** inconclusive input capture or tool verification.
`--json` always emits one `rvw.cosim/1` object on stdout. Human output includes the
first mismatch's index, order, cycle, PC, disassembly, expected/actual effects,
last `--history K` matching instructions and integer register-file diff.
A match does not mean the program passed; `end_status` preserves the trace's
termination status. A trace without an end event is explicitly a matching prefix.

### What "match" guarantees

Exit 0 means: every traced instruction and trap event agrees with the reference in the
compared fields (see "Comparison and synchronization"), after the listed synchronizations.
Version 1 does not check floating-point registers or `fflags`/`fcsr` state.
Version 2 compares raw FP writes and post-instruction `fflags`/`fcsr` with Spike.
Sail refuses these fields because its effect interface lacks them. Neither version checks CSR side effects that
no traced instruction reads, memory that no traced instruction reads, or timing. A matching
**prefix** (no end event, `trace_complete: false`) also exits 0, and so does a trace that
ended in `fail` or `timeout`. Agents must check `trace_complete` and `end_status`, and read
`recent_synchronizations` and `recent_quirks` for what was taken from the core.

## Platform configuration

Use `--core LABEL --platform /path/platform.json` for another core:

```json
{
  "name": "example", "xlen": 64, "isa": "rv64imafdc_zicsr_zifencei",
  "reset_pc": "0x80000000", "pmp_regions": 8, "aligned_mem": false,
  "ram": [{"base": "0x80000000", "size": "0x10000000"}],
  "mmio": [{"base": "0x02000000", "size": "0x10000"}]
}
```

Platform policy keys are explicit in the BOOM and VexRiscv JSON files:

- `privilege_modes`: `M`, `MU` or `MSU` (default `MSU`). Spike receives this value.
- `misaligned`: an object with `load`, `store`, `atomic`, `split_page` and
  `split_bus`. Loads and stores must both select `trap` (default), or both
  select `emulate`. With `trap`, `atomic` must be `trap`. With `emulate`,
  `atomic` must be `access_fault`, the installed Spike outcome. Alignment
  traps use causes 4/6; atomic access faults use causes 5/7. Trap events compare
  the failing address in `tval` without a mask.
- `split_page` and `split_bus` must be `refuse`. Scalar C2 cannot describe
  partial writes, bus fault precedence or intermediate transactions. Completed
  accesses across an XLEN word, and multiple reference memory effects, are
  refused. XLEN is the trace word boundary, not a claim about physical bus width.
  An alignment trap before a split compares as a trap. Partial effects and fault
  precedence after a split are outside this comparison. Other policies are refused.
- `endianness`: an object with `instruction`, `data`, `page_table` and `device`.
  Each must be `little`. Other combinations are refused before model execution.
  This declaration does not establish big-endian support.
- `absent_pmp_csrs`: `trap` (default), or `read_zero_write_ignored` with
  `pmp_regions: 0`. The latter installs constant-zero PMP CSRs in Spike.
  Writes have no effect. Normal CSR privilege checks still apply. RV64 odd
  `pmpcfg` addresses remain illegal. This applies only to `0x3a0..0x3ef`.
  Other CSR accesses, wrong read values and unexpected traps still mismatch.
- `ecall_tval`: `zero` (default) or `insn` (exactly `0x73`). Only a matching
  synchronous ECALL cause 8, 9 or 11 can use this rule. The checker sets the
  reference trap CSR to that declared value for later reads. Other causes and
  other values still mismatch. This is a platform rule, not synchronization;
  `--strict` retains it. Without a trap event, C2 cannot check `tval`.

VexRiscv declares zero PMP reads with ignored writes and ECALL `tval=0x73`.
BOOM retains its previous outcomes. Sail currently refuses non-MSU modes,
misaligned emulation, zero absent-PMP CSRs and nonzero ECALL `tval`.
It does not silently replace these settings with its defaults.

`aligned_mem` selects RVFI's `RISCV_FORMAL_ALIGNED_MEM` convention: word-aligned
addresses with masks/data shifted into the active byte lanes. It defaults to
false for access-relative addresses; BOOM sets it true. Reference effects and
MMIO inputs are converted through that explicit convention.

RAM must be page aligned; all ranges must be nonoverlapping. ELF PT_LOAD segments
(file bytes and BSS) must lie wholly in RAM, for Spike and Sail (one shared check). Segments
and BSS start from a fresh, zero-filled machine. Both models fault an access outside `ram` and
`mmio`; Sail also needs page-aligned MMIO ranges (see "Sail offline checker").
The reset PC is explicit, rather than inferred from the first trace PC. Only
little-endian, statically linked RISC-V ELF32/ELF64 images are supported. Trace
XLEN and ISA must exactly match the selected platform. Implementation-specific
WARL CSR behavior and extension sets need a matching platform/model configuration.

The BOOM config describes the simulation's 256 MiB RAM, CLINT, interrupt
generator, Zba/Zbb/Zbs extensions and aligned RVFI memory lanes. No BOOM signal names, test paths or interrupt addresses appear in the
generic comparator. It models standard MSU privilege and eight PMP regions;
select another `pmp_regions` value when needed.

`reference_isa` optionally gives the reference model's explicit ISA spelling.
BOOM's adapter uses the older ISA string which omits the separately named
Zicntr/Zihpm extensions, although its CSR implementation exposes those counters.
Its config explicitly adds them for modern Spike. This translation is configured,
never inferred from successful core execution; other platforms default to `isa`.
The trace header must still exactly match `isa`.

Optional keys describe implementation choices and known trace quirks. Each is
narrow, and every use is listed in the result (`recent_quirks`, `recent_synchronizations`):

- `csr_masks`: per CSR (number or range such as `"0x3b0-0x3b7"`), the mask of its
  implementation-defined bits. A read of the CSR takes those bits from the core; all other
  bits compare strictly, including the old value returned by CSRRW/CSRRS/CSRRC. `pmpaddr`
  entries beyond `pmp_regions` are refused. BOOM: `misa` `0x6` (bit 1: BOOM does not report
  B, which Spike sets for Zba+Zbb+Zbs; bit 2: BOOM's misa.C is read-only, Spike lets
  software clear it), `mvendorid`/`marchid`/`mimpid` all bits, `tdata1` all bits (BOOM has no
  triggers), `pmpaddr0`-`pmpaddr7` bits 30 and up (BOOM keeps 32-bit physical addresses).
  The old `csr_sync` key (whole values) is refused.
- `trace_from_reset` (default `true`): the trace starts at reset, so `instret`/`minstret`
  reads compare strictly. Set `false` only for a trace that starts later; then the first
  RV64 instret read sets Spike's retirement counter to the core's value. BOOM does not set it.

- `illegal_insn_tval`: `"insn"` (default, Spike's choice) or `"zero"`. The spec lets a
  core write zero to `xtval` on an illegal-instruction trap. With `"zero"`, a zero
  `tval` is accepted for cause 2 only, and the reference model's `mtval`/`stval` is
  set to zero so later reads agree. BOOM sets `"zero"`.
- `mode_after_change`: `true` when the core's RVFI reports an instruction that changes
  privilege (a trap, `mret`, `sret`) in the new mode instead of the mode it ran in.
  The reported mode must equal the reference model's mode after the instruction;
  any other value is still a mismatch. BOOM sets it: its RVFI `mode` reads the CSR
  file's current privilege at commit, which has already changed (`rvfi.scala`,
  `r.mode := io.prv`). This is a bug in BOOM's trace port, not in the core's
  architectural behaviour; remove the key once the port is fixed.

## BOOM results

`small`, fixed memory latency 20, seed 1, riscv-tests `rv64{ui,um,ua,uf,ud,uc,mi,si,uzba,uzbb,uzbs}-p-*`
(174 tests, including the misaligned-access, page-fault and PMP tests), traces made on
2026-10-21 with the adapter at this revision: 173 match Spike instruction for instruction.
Rerun with the round-2 adapter (irq level events, xepc check): the same 173 match and 1 mismatch;
no trace needed an `irq` synchronization; no run ended `assert` from the xepc check; every trace
has one `irq` event (all inputs low).

- `rv64mi-p-instret_overflow` **mismatches**: after `csrwi minstret,0`, `csrr a0, minstret`
  returns 1 on BOOM and 0 on Spike. This is a known BOOM core divergence (the core test also
  fails); it is not fixed here. Earlier versions synchronized the first instret read and
  reported a match, which hid it.
- `rv64ui-p-ma_data` matches but ends with `end_status: fail`, as the core's own
  `RiscvTestsSpec` expects.

BOOM's adapter writes trap `tval` one cycle after the exception (BOOM's trace drives it late).
ECALL/EBREAK are plain retirements in BOOM's commit trace; their trap events carry the
`mcause`/`mtval` (or `scause`/`stval`) values read from BOOM's CSR file, made `simPublic` by
the adapter. The adapter does not compute these causes. These registers have no write strobe,
so the adapter also requires `mepc` (or `sepc`) to equal the ECALL/EBREAK's PC; otherwise the
cause could be left from an earlier trap, and the run ends with status `assert`. (Not shown
failing: that needs a core that does not write the trap CSRs. A repeated ECALL at the same PC
whose trap is lost would still pass this check.)

WFI: a hart may leave WFI at any time, so the Spike shim never stays asleep after
`wfi`; an interrupt in the trace still arrives through its trap event. (Tested:
`program_traps.S`.)

## Comparison and synchronization

The checker compares PC, next PC, instruction encoding (16 bits for compressed),
privilege, synchronous trap flag, integer destination and value, memory virtual
address, read/write byte masks, active memory data lanes, and memory fault flag.
Unused memory data lanes and rd=x0 data are unspecified and ignored. Instruction orders start at zero and cannot have gaps. The input is
streamed; retained history and register state are bounded. Integer register diffs
reconstruct the core state from its traced writes, assuming architectural reset.

Pure reads of cycle/mcycle, time, and standard HPM counters, including RV32 high
halves and machine aliases, use the core's destination value (sync kind `counter`).
instret/minstret reads compare strictly for a trace from reset (`trace_from_reset`).
Only with `trace_from_reset: false` does the first RV64 instret read set Spike's
retirement counter (later reads compare strictly); RV32 halves then take the core's value.
The reference instruction must still execute legally with the same instruction,
PC and destination. CSR operations which modify a counter are compared strictly.

Reads of `mip`/`sip` may take an external-input bit (MSIP, MTIP, SEIP, MEIP) from the core
(sync kind `irq`), with three limits. (1) Only a 1 the reference lacks: an input ORs into the
bit, so a core that reads 0 where the reference has 1 (for example SEIP that software set with
`csrs mip`) mismatches. (2) Only with evidence that the input was high. A trace with C2 `irq`
level events (the adapter writes the input levels it drives) gives it: the input was high at
some cycle from `irq_input_latency` cycles (platform key, default 4, not measured on BOOM)
before the previous retirement up to the read. The checker keeps only per-bit state (the cycle
the bit was last set high, and the cycle it went low after that), so memory does not grow with
the number of level events. Level events apply by cycle, not by their place in the file: C2 lets
the records of cycle N come before the `irq` event of cycle N, so the checker reads one cycle at a
time and applies that cycle's level events before its instruction and trap records. An event of
a later cycle never counts for an earlier record. A trace with more than 4096 records in one
cycle is refused (exit 2). A trace without level events gives it only
inside the handler of an interrupt with that cause, from its trap event up to the next xRET.
(3) Software-written bits (SSIP, STIP, ...) always compare strictly. With no interrupt and
no level event, every `mip`/`sip` bit compares strictly. `csr_masks` reads are sync kind
`csr`; MMIO loads are `mmio`.

Every synchronization is logged (total, bounded recent history, with CSR and mask for `csr`
and `irq`). A masked read whose value already agrees is not counted. `--strict` disables all
kinds; `--strict-sync csr,irq` disables only the listed kinds (MCP: `strict_sync`). The
result lists `sync_enabled`.

Loads wholly inside configured MMIO ranges supply the core's raw load data to the
reference device callback. Spike performs the actual sign extension and register
write; the checker checks consistency between raw data and the core destination,
then keeps that value for dependent instructions. MMIO address, width and operation
still compare exactly. Unmapped accesses remain faults. RAM load data is never
substituted. MMIO stores are inert; timing and interrupts come from the trace.
This is suitable for nondeterministic reads, not a device behavioral model.

Spike's installed load commit log has address/size but no raw read value. The shim
reads ordinary load data back through the reference MMU and snapshots AMO input
before execution, including AMOs with rd=x0. Configured MMIO reads are inert, so
observation does not acknowledge devices twice. A future device model with read
side effects needs a load observation hook instead.

Synchronous traps can be represented by a `trap=true` instruction followed by an
optional trap event, or by a standalone trap event without a retired instruction.
Trap events compare reference cause and tval. A synchronous event may precede
or follow its matching trap instruction record; both are checked once against
the same reference exception. Without an event, C2 cannot provide
cause/tval, so only the trap flag and instruction effects can be checked.

An interrupt requires a C2 `event=trap` carrying the interrupt cause before the
first handler instruction. If the cause is a platform input (platform key `irq_inputs`,
default MSIP, MTIP, SEIP, MEIP = 3, 7, 9, 11), the shim asserts that pending bit for this
one step and then restores the bit's earlier value: a bit that software set (an `mip` write,
or SEIP written by software) stays pending. Any other interrupt (SSIP, STIP: only software sets
them) is not injected: the reference must take it from its own `mip`/`mie` state, otherwise the
trap event mismatches. Spike checks privilege, enable and delegation and enters its
own trap handler. The checker verifies cause/tval, then requires RVFI `intr=true`
on the first handler instruction. Synchronous traps also require that first-handler
marker, including when no separate trap event is present. It does not force-enable interrupts or rewrite
trap CSRs to agree with the core. A spurious intr flag, disabled interrupt, wrong
cause or incorrect handler PC is a mismatch. The trace says when an external
interrupt occurred; the checker cannot independently prove external timing. When the trace
has C2 `irq` level events, an interrupt from a platform input is injected only if that input was
high at some cycle from `irq_input_latency` cycles before the previous retirement up to the trap
(the same window as the `mip`/`sip` evidence). A trap whose input stayed low is not injected and
is a mismatch (difference `irq_input`). Without level events the trap event alone gives the
interrupt and its timing (unchanged).

## Sail offline checker

```sh
RVW_SAIL=/path/sail_riscv_sim rvw/.venv/bin/rvw cosim check \
  --trace run/rvfi.jsonl --elf /path/test.elf --core boom --model sail --json
```

Sail executes the ELF independently using its public trace interface. The parser
reads instruction, integer register, memory, CSR, page-walk, exception and interrupt traces,
obtaining next PC from one-instruction lookahead. `--sail-config FILE` supplies the base Sail
configuration (otherwise Sail's defaults for the platform XLEN); the platform's
`sail_overrides` tune that config. The checker then applies the platform ISA, XLEN,
PMP count, memory map and illegal-instruction `xtval`. It writes one complete config.
Sail must validate that config and report the expected ISA with `--print-isa-string`
before it executes the ELF. Missing or extra extensions cause an error.
`--timeout` bounds each config query and the execution subprocess. The supported
ISA spellings and the audit of platform settings are in
[Decisions](#decisions).

Sail's memory map is the platform's. The complete config replaces Sail's
`memory.regions` (its default has 2 GiB of RAM from `0x80000000` and a ROM at `0x1000`): each
`ram` range is main memory and each `mmio` range is I/O memory (not executable), with the
attributes of Sail 0.15's default RAM and MMIO regions. Nothing else is mapped, so an access
outside the map faults as on the core's bus. A map Sail cannot represent is an error: a range
that is not page aligned, `sail_overrides` that set `memory.regions`, or (Sail's own validation)
its CLINT or test interrupt device outside every `mmio` range. A fetch fault (Sail prints no
instruction line for it) is a step of its own: `insn` 0, `trap`, `mem_fault`, as in Spike.

BOOM's `sail_overrides` (in `configs/boom.json`) describe what Sail must know about BOOM:
only BOOM's extensions (RV64IMAFDC, Zicsr, Zifencei, Zicntr, Zihpm, Zba/Zbb/Zbs, S, U,
Sv39); read-only `misa`; misaligned loads, stores and AMOs trap; 8 PMP entries and 32
physical address bits; `medeleg`/`mideleg` delegable bits `0xb15d`/`0x222`; `marchid` 2;
Svade (a clear A/D bit faults, BOOM does not update it in hardware); trigger CSRs present
(Sdtrig with one trigger, as Sail needs at least one).

What Sail checks. Sail starts at the ELF entry, which must equal the platform reset PC. It
compares the same fields as Spike. It stops at its own HTIF termination (the `tohost` store);
the comparison ends there, the result scope is `until the reference's termination`, and
`uncompared_instructions` counts the core's records after that point (BOOM retires one more
instruction, the `j` after the store, before its harness sees the store). The core's end status
must agree with Sail's (`reference_end`), otherwise it is an error. This also holds when the core
trace ends at the tohost store itself (then `uncompared_instructions` is 0 and the scope is
`complete trace`). A core end status is not checked when Sail did not stop at that point. Memory addresses are the
virtual addresses (rs1 + offset, decoded for the platform's XLEN: on RV32 the compressed
funct3 3/7 forms are c.flw/c.fsw/c.flwsp/c.fswsp, on RV64 c.ld/c.sd/c.ldsp/c.sdsp; Sail logs
physical addresses, and the page offsets must agree);
page-walk reads and page-table A/D writes are not instruction accesses and are dropped.
Supervisor software and timer interrupts (pending bits only software sets) are taken by Sail
itself; the core's trap event must agree in place and cause.

What Sail cannot check. Sail cannot take values from the core (no synchronization): a trace
that needs one (a `csr_masks` read that differs, an MMIO or counter read, an interrupt from an
input: MSIP, MTIP, SEIP, MEIP) is an error (exit 2), never a match. The shared checker applies
`mode_after_change` using the mode of Sail's next traced instruction. The generated config
sets `base.xtval_nonzero.illegal_instruction` from `illegal_insn_tval`. Unselected instruction
and privileged extensions stay off, including Sstvala, Shtvala, Shvstvala and Sha.
Virtualized modes (Sail `[VS]`/`[VU]`) are rejected.
The Sail executable comes from `--sail` or `RVW_SAIL`; over MCP only from `RVW_SAIL`.
Unsupported textual trace formats, exception or interrupt names fail closed. This backend
targets Sail 0.15's text format.

Sail on the 174 BOOM traces (round-2 review, same runs as "BOOM results" below, traces with the
round-2 adapter): **171 match** (all up to Sail's termination, one uncompared core instruction
each; `rv64ui-p-ma_data` ends `fail` on both). **3 errors, none a match**:
`rv64mi-p-instret_overflow` and `rv64mi-p-zicntr` read counters (nondeterministic: rejected
before running); `rv64mi-p-breakpoint` reads `tdata1`, which BOOM implements with no triggers
(reads 0) and Sail cannot (it needs at least one trigger), so the masked read needs a value from
the core. Spike remains the reference for those three. Rechecked in round 4 with Sail on the
platform memory map (same traces): the same 171 match and 3 errors, with the same scopes, end
statuses and uncompared counts.

## Generate traces and test

```sh
rvw/.venv/bin/rvw cosim generate --elf /path/rv64ui-p-add --core boom \
  --out /tmp/add.jsonl --json
rvw/.venv/bin/rvw cosim check --elf /path/rv64ui-p-add --core boom \
  --trace /tmp/add.jsonl --json
rvw/.venv/bin/python -m pytest rvw/tests/cosim -q
rvw/.venv/bin/python Cosim/smoke.py --isa-dir /path/riscv-tests/build/isa \
  --bench-dir /path/bench/build/bare --out /tmp/cosim-smoke.json
```

Generation runs Spike's library directly and serializes architectural effects to
C2. It stops at an odd `tohost` write, WFI, or `--max-instructions` (default 1M).
It emits a trace prefix at the limit. It does not implement HTIF host syscalls.
Source-register fields are generated from pre-instruction integer state and a
small scalar IMAFDC encoding decoder. Architectural execution remains in Spike.
Roundtrips exercise bindings and conversion; they are not independent ISA proof.
Sail comparison supplies a second implementation for deterministic programs.

The smoke command captures the selected ELF list and every ELF before its first
run. It uses the same captured platform, shim, linked Spike library, interpreter
and probe sources for the whole batch. The JSON output stays a list. Row 0 holds
the shared `capture` record; each row has `capture_row: 0` and its captured ELF
hash. The command verifies tools and publishes the complete list by atomic rename.
An empty input set or failed capture is inconclusive, exit 3. It cannot produce a
successful empty smoke run.

Pytest compiles a tiny committed assembly source at test time, with RISC-V GCC
(`RISCV_GCC` may select it), and uses the real Spike library. It exercises correct
execution, valid and masked interrupts, trap-only events, counter and MMIO value
changes with dependent instructions, memory lanes/AMOs, and mutations of rd data,
branch next PC, trap presence/cause, intr, privilege, memory address/masks/data.
It also checks CLI 0/1/2/3 exits and validates the C2 and Sail parsers. Native tests
skip explicitly when the shim or compiler is absent; build them for acceptance.
Large traces are temporary and never committed.

## Decisions

- Use Spike's public step API. Commit effects and CSR values come from the library.
  Diagnostic output identifies trap entry because public state has no per-step
  exception callback. Serialize all native calls because libriscv is not thread-safe.
- The platform ISA is authoritative. Do not infer extensions from an ELF or trace.
  Generation refuses unknown successful instructions, including unsupported operands.
  Unknown trapping instructions can still be recorded as traps.
  `reference_isa` can translate legacy extension names for the reference model.
- Preserve observed differences before synchronization. Wrong instructions,
  addresses, masks, traps and destinations must still fail. Counter-writing
  instructions compare strictly. CSR synchronization changes only configured bits.
- Interrupt injection supplies timing, while Spike checks enable and delegation.
  Inject only declared `irq_inputs`. Preserve pending bits set by software.
  SSIP and STIP come from reference state. Level evidence applies to every record
  in the same cycle, in either file order. Refuse cycles with more than 4096 records.
  Later cycles cannot supply evidence for an earlier trap or CSR read.
- Check recorded execution even when it ends with fail or timeout. A matching
  prefix is still a prefix. No comparison result establishes program success.
- Each CLI or MCP command captures the ELF, trace, platform, explicit Sail config,
  adjacent C1 and any existing output needed by the overwrite guard once.
  Models consume private copies. Reproduction metadata keeps source paths,
  resolved paths, hashes, sizes and symlink provenance. It omits temporary `copy` paths.
- Capture the shim source, build code, Spike headers, three link libraries,
  compiler identity, flags and build environment before compilation. Compile
  private copies. The dependency file must list only captured user headers.
  System headers and compiler support files use C8's installed-toolchain assumption.
  Verify inputs and tools before publication. The manifest binds output bytes to
  the build record. The binary embeds the build ID. A stale build requires a rebuild.
  Binary and manifest use separate atomic replacements; a mismatched pair refuses.
- Runtime checks the source, shim, manifest and linked libriscv hashes and embedded
  identity. Load private binaries and check the actual dependency binding and shim
  mapping. An unsupported loader or incompatible existing mapping is inconclusive.
  The installed `spike` executable does not run the model or supply its identity.
- Capture `RVW_SPIKE_SHIM`, `RVW_SAIL`, `PATH`, `PYTHONPATH`, `DYLD_LIBRARY_PATH`,
  `DYLD_INSERT_LIBRARIES`, `LD_LIBRARY_PATH` and `LD_PRELOAD`. Refuse nonempty loader
  overrides. Pin Sail, git and the resolved Python probe interpreter. The probe
  imports a captured `rvw/src` tree. The captured tools revision does not prove
  that the worktree is clean.
- Query Sail's default config once at command start and record the exact text.
  An explicit config is a captured file. The model API receives prepared inputs.
  Sail confirms its full effective ISA before executing. Config queries and
  execution have process-group timeouts. Unsupported config structures refuse.
- Sail supports RV32/RV64 IMAFDC, G, Zicsr, Zifencei, Zicntr, Zihpm, Zba, Zbb,
  Zbs, Zmmul, Zaamo, Zalrsc, Zca, Zcf and Zcd spellings. Expand dependencies and
  check reported capability aliases. Refuse other extensions and versioned names.
  A complete Zca/Zcf/Zcd set can imply C; partial sets stay partial.
- Sail uses MSU with H off. Page modes default to Bare and Sv32 for RV32, or Bare,
  Sv39, Sv48 and Sv57 for RV64. Explicit `Sv*` settings tune these modes.
  BOOM selects Sv39 and Svade. Platform PMP count sets usable entries in Sail's
  0, 16 or 64-entry bank. Extra entries read zero. Physical address width, PMP
  grain, page-table policy and `mutable_misa` come from the base config or overrides.
  BOOM uses 32 physical address bits and read-only `misa`.
- Sail executes independently. It cannot synchronize state from the core.
  Reject nondeterministic counter/MMIO reads and platform input interrupts.
  `irq_inputs`, latency and `trace_from_reset` cannot enable offline synchronization.
  Its parser removes an A/D write only after a successful matching page-table walk.
  Check PTE address, size, changed bits and access direction. Unexplained writes
  and ambiguous store attribution refuse.
- Generation refuses an ELF alias, directory, unrelated file or recorded core
  trace as output. Only an earlier reference trace can be replaced. Publish by
  atomic rename after tool verification. Smoke tests reuse a private reference
  trace across ELFs, capture the whole batch first and publish one complete list.
- Capture failures return inconclusive, exit 3. Invalid captured data returns
  error, exit 2. No result after a failed input check can be a match.
  Results have no complete cache key. System libraries, Python's standard library
  and other implicit runtime dependencies are not fully enumerated.

## Limits and next work

C2 version 1 contains no FP writes or CSR snapshots. Version 2 adds them;
Spike compares them and Sail refuses unavailable observations. No vector/multi-
access instruction, debug-mode execution, multiple harts, H extension, or device
model is supported. `halt` is retained as input metadata; WFI is not RVFI halt.
Optional version 2 fault-access records check supported zero-completion attempts.
Other fault effects remain unsupported.

Real-core validation depends on the separately built BOOM adapter. Run its C1
command with `--rvfi-trace`, then the same `cosim check` command on the resulting
trace. Wrap BOOM builds/simulations in `scripts/with-lock.sh boom ...` and use only
`../spinal-boom-eda`; never build or write the primary core checkout.

## MCP tools

`rvw mcp` discovers `cosim_check` and `cosim_generate`. Use check to compare a recorded trace
with Spike or Sail and find the first architectural mismatch. Supply `elf`, `core`, `trace`,
and optionally `platform`, `model`, `history`, `strict`, `strict_sync` (kinds to disable:
`counter`, `mmio`, `csr`, `irq`), `sail_config`, `timeout`. The Sail executable comes only
from `RVW_SAIL` on the server, never from an argument. Check is read-only. Use generate with
`elf`, `core`, `out` and optional `max_instructions` to write a bounded Spike reference trace;
it refuses an `out` that is the ELF, a directory, an existing file that is not a C2 trace, or a
C2 trace recorded from a core (it replaces only an earlier reference trace).

Both return a job ID. `job_status(wait_s=60)` returns the same JSON as the corresponding CLI
`--json` command, including reproduction metadata and mismatch/error or prefix/end status.
`job_cancel` stops the worker and model subprocesses. Matching execution still has the scope
and synchronization limits described in the main README ("What match guarantees"):
version 1 excludes FP state and unread CSR state. Unread memory remains unchecked; a matching prefix also returns
`match`. It is not proof that the program passed: check `trace_complete` and `end_status`.

## Architectural comparison coverage

This matrix describes the current C2 contract and comparators. It does not add
features or claim independent-reference experiment results. A match applies only
to the fields and recorded execution below.

| State or effect | C2 evidence | Spike | Sail |
|---|---|---|---|
| PC, next PC, instruction, privilege | Per instruction | Compared; declared mode-after-change quirk | Compared; same quirk |
| Integer destination and value | Per instruction | Compared; declared synchronization below | Compared; external values cannot be injected |
| Integer source operands | Present in C2 | Not directly compared; later effects can expose errors | Same |
| Scalar memory address, masks, active bytes, fault flag | Per instruction | Compared; inert MMIO load data synchronized | Compared; model device behavior, no external data injection |
| Trap cause and failing address (`tval`) | Optional trap event | Compared; exact declared illegal/ECALL value | Compared; unsupported ECALL policy refused |
| CSR read result | Integer destination | Compared except declared masks, counters and evidenced input bits | Compared; nondeterministic reads refused |
| Unread CSR state and CSR side effects | Optional version 2 post-instruction snapshots | Exact declared CSR set | Snapshots refused |
| Cycle/time/HPM read | Integer destination | Synchronized on pure reads; strict mode disables this | Refused when offline synchronization would be needed |
| instret/minstret | Integer destination | Strict from reset; declared late-trace offset only | Compared; no external offset injection |
| MMIO and interrupt external inputs | Optional IRQ levels, load result and trap event | Declared MMIO/input synchronization; not a device or timing proof | External-input synchronization unsupported; nondeterministic traces refused |
| FP registers, `fflags`, `fcsr` | Required version 2 fields | Exact raw write and post-step flags | Version 2 fields refused |
| Vector, hypervisor state | No matching state contract | Out of scope; scalar-unrepresentable effects refused | Unsupported ISA/virtualized modes refused |
| Debug state | No debug state contract | Debug execution refused | Unsupported execution refused; no debug-state comparison |
| Per-hart state, inter-hart order | No hart identity or shared-memory order | Single hart only; multi-hart out of scope | Same |
| Fault attempts and partial memory effects | Optional version 2 attempt/completion masks | Supported zero-completion scalar attempts; partial effects refused | Fault-access extension refused |
| Endianness | Platform declaration, little-endian ELF | Little only; other combinations refused | Little only |
| PMP TOR/NA4/NAPOT, priority, grain, locked entries | Only observed instruction effects | Model execution; no claim of a complete coverage suite | Same |
| Halt/WFI and timing | C2 halt/cycle fields | No cycle or halt equality; WFI may resume | No timing proof |

Dependencies: [#10](https://github.com/riscPrint/risc-v-workstation/issues/10)
(FP state), [#47](https://github.com/riscPrint/risc-v-workstation/issues/47)
(interrupt stimulus), and [#75](https://github.com/riscPrint/risc-v-workstation/issues/75).
Related scope: [#87](https://github.com/riscPrint/risc-v-workstation/issues/87),
[#114](https://github.com/riscPrint/risc-v-workstation/issues/114),
[#136](https://github.com/riscPrint/risc-v-workstation/issues/136),
[#90](https://github.com/riscPrint/risc-v-workstation/issues/90), and
[#100](https://github.com/riscPrint/risc-v-workstation/issues/100).

## Adapter interrupt regression

See [RiscvSim interrupt schedules](../RiscvSim/README.md#interrupt-schedules).
`rvw/tests/interrupts/window_check.py` checks independently supplied cycle and
PC bounds, input changes and the test program's trap-entry state. It does not
replace Spike instruction comparison. Spike injection still uses C2 trap events;
a Spike match alone does not prove legal interrupt timing. The regression checks
both results. Missing independent bounds stays inconclusive. Sail still refuses
external-input synchronization.

## Limit ownership

FP state: [#10](https://github.com/riscPrint/risc-v-workstation/issues/10). Unread CSR effects: [#87](https://github.com/riscPrint/risc-v-workstation/issues/87). Faulting accesses: [#93](https://github.com/riscPrint/risc-v-workstation/issues/93). Hypervisor state: [#114](https://github.com/riscPrint/risc-v-workstation/issues/114). Debug state: [#136](https://github.com/riscPrint/risc-v-workstation/issues/136). Multi-hart: [#90](https://github.com/riscPrint/risc-v-workstation/issues/90). Vector tests: [#75](https://github.com/riscPrint/risc-v-workstation/issues/75). WFI: [#149](https://github.com/riscPrint/risc-v-workstation/issues/149).

Retained limit: The comparison matrix bounds every match. Synchronization is not a timing or device proof. Little-endian scalar C2 evidence, refused unknown input structures and incomplete runtime dependency capture remain explicit restrictions.
## Reference interrupt devices

`rvw.cosim.devices.Plic` is a deterministic level-triggered PLIC reference.
`PlicMap` takes absolute register addresses and dimensions from the caller.
It supports priority, threshold, enable words, pending bits and claim/complete.
Source zero is reserved. Equal priorities select the lowest source ID.
Claim ignores the threshold. Completion reopens the level gateway.
Calls form one ordered sequence. Apply concurrent inputs in a declared order.
Unmapped or unsupported access widths raise `ValueError`.

Run the directed suite and native Spike oracle:

```sh
RVW_DEVICE_SPIKE_PREFIX=/path/to/spike nice -n 10 rvw/.venv/bin/python -m pytest \
  rvw/tests/devices -q
```

The prefix must have matching Spike headers and libraries. The tests compile
`spike_devices.cc` and use Spike's `plic_t` directly. The oracle uses two harts
with M/S contexts. Native oracle tests skip when the prefix is absent.
The Python model has global pending state and level gateways. Spike's device
has its own context bookkeeping. Oracle tests cover only the common sequence
in the test. They do not establish equivalence for all context races.
These models do not connect an RTL bus or establish DUT device coverage.
The current BOOM and VexRiscv adapters do not implement a PLIC.

### Decisions and limits

Keep addresses and context dimensions in project data or caller data.
Keep reference-device tests separate from instruction co-simulation.
Do not use a DUT MMIO read as the expected device state.
Edge gateways, bus errors, asynchronous CDC and arbitrary PLIC register WARL
behavior are outside this model. `max_priority` must be a contiguous low-bit mask.

### Timer and software interrupts

`Timer(TimerMap.from_dict(data['timer']))` loads a declared map from JSON.
See `examples/boom/devices.json` and `examples/vexriscv/devices.json`.
The examples declare reference maps. They do not install devices in the adapters.
BOOM's timer addresses match its current memory map. Its `intGen` at
`0x0c000000` is not a PLIC. Do not replace it with the reference PLIC implicitly.
VexRiscv has only scheduled interrupt inputs and no MMIO timer device.

`Timer` supports CLINT and relocated ACLINT MTIMER/MSWI registers, one compare
and software register per declared hart. Call `tick(n)` to advance time.
Use aligned 32-bit split accesses or aligned 64-bit timer accesses.
Software registers retain bit zero only. IRQ bit 3 is MSIP; bit 7 is MTIP.
MTIP asserts at unsigned `mtime >= mtimecmp`. Time wraps at 64 bits.
Reset values come from project data. They are not architectural reset guarantees.
The native oracle compares CLINT accesses, split writes and two-hart IRQ state
with Spike's `clint_t`. Relocated ACLINT accesses have model unit tests only.
ACLINT SSWI, bus timing and a native ACLINT oracle remain unsupported.

### Reset state observer

`rvw.cosim.reset.check_reset` checks samples against `ResetContract`.
Supply expected state values and masks from the project's reset contract.
Supply the valid outputs that must stay low during reset.
Capture an asserted sample and a released sample from the same DUT instance.
Select the post-release state-check boundary before the run.
Check each cold, warm, local or repeated pulse separately. Warm and local
retention values must come from the project. The observer does not choose them.

The result is `consistent`, `mismatch` or `inconclusive`.
Missing state, output values, pulse evidence or contract gives `inconclusive`.
A measured conflicting value gives `mismatch`.
The observer does not assert reset or prove that an adapter sampled a DUT.
`test_reset.py` checks observer fixtures and repeated reference-device reset
while IRQs and a PLIC claim are active. These are not RTL reset results.
Real core reset during bus, trap and debug activity remains unsupported here.
Do not use simulator initialization as a reset sample.

### Version 2 FP state

Use `rvw.rvfi/2` with the required fields defined in C2. Spike shim ABI 4 exports
raw FP writes, including f0, and post-step `fflags` and `fcsr`. Comparison uses
all 64 FP data bits. No FP data or flag field permits synchronization. Legacy
BOOM traces remain version 1 and cannot establish FP register coverage. The
reference generator still emits version 1. Adapters must capture DUT state;
they must never fill these fields from Spike.

### Unread CSR state

Version 2 adapters can declare `csr_snapshot` addresses and emit `csr_state`
after each instruction. Spike reads its own CSRs through its public peek API.
The comparison uses full values and does not use `csr_masks`. Include mstatus
or sstatus to check FS dirty-state transitions. The adapter must resolve the
state after each retirement, including each slot of a multi-retire cycle.
Only the declared CSR set is covered. Sail has no snapshot API and refuses
these records. Timing-dependent CSRs need an agreed observation point.

### Fault-access records

C2 version 2 separates attempted data accesses from completed `mem_*` effects.
`fault_access` uses access-relative byte lanes even with `aligned_mem=true`.
Spike checks zero-completion uncompressed scalar loads/stores (width codes 0..3)
using reference operands. Partly completed faults, compressed attempts, unsigned
load width codes and AMOs are refused. Sail refuses this extension. Null means
unobserved data. Neither checker fills missing DUT data from the reference.

### Live retirement integration API

`rvw.cosim.online.check_online(stream, model, platform, stop=stop_sim,
reproduction=identity)` checks a flushed text JSONL stream during simulation.
`identity` must come from the same captured ELF, platform and reference inputs
used to start the model, using `Inputs.metadata()`. The caller owns the stream,
model lifetime, wall timeout and simulator process group. `stop_sim` must stop
and reap that group, for example with `rvw.common.proc.kill_group`. The checker
calls it at the first checked mismatch or parse/reference error. This API uses
the offline comparison and synchronization report without a second policy.

Cycle grouping needs one later-cycle line before checking the preceding cycle.
A producer must flush each line. It must provide a wall timeout for a stalled
producer. The result reports the digest and line count of the consumed prefix,
including lookahead. It never calls that digest a complete input trace hash.
EOF before an end event is inconclusive. Save the complete stream for offline
replay. The CLI and the BOOM adapter do not yet launch this API. This increment
provides the generic integration point, not BOOM online runtime evidence.
