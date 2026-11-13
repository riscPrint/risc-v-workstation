# Debug transport, Debug Module compliance and instruction trace

`rvw debug` checks simulated debug targets and baseline E-Trace streams.
It has a reference model of the Debug Module, JTAG and DMI drivers, a
remote_bitbang server, a self-checking compliance campaign and a TAP/DTM
campaign. A reference-model pass does not prove a core implementation.

## Debug profile

A debug profile (`rvw.debug-profile/1`, TOML) declares the option set of one
target. Put it beside `rvw.toml` and name it in `[debug_module] profile`, or
give `--profile`. The campaigns test only declared options. A check for an
undeclared option is `unsupported`, never a pass. `[skip]` maps a check id to a
reason; a skipped check is listed with its reason and is not a test.

| Key | Meaning (default) |
|---|---|
| `version` | `"0.13.2"` or `"1.0"` (`"1.0"`) |
| `xlen`, `harts`, `hartsellen` | 32 or 64; hart count; implemented hartsel bits (from `harts`) |
| `unavailable`, `hart_array`, `haltgroups` | unavailable hart indices; hasel window; dmcs2 halt groups |
| `progbufsize`, `impebreak`, `datacount`, `autoexec`, `postincrement` | program buffer and data registers |
| `abstract`, `aarsizes`, `csr_missing_cmderr` | command kinds (`gpr`, `csr`, `fpr`, `memory`, `quick`); sizes; cmderr for a missing CSR (2) |
| `hartreset`, `resethaltreq`, `reset_vector` | reset options and the reset PC |
| `modes`, `scratch`, `memory` | privilege modes; RAM the campaign may overwrite (code at +0, handler at +0x400, data at +0x800, U code at +0xc00); memory regions with `kind` ram/readonly/error/off and `sberror` |
| `[triggers]` | `count`, `types` (2 mcontrol, 3 icount, 4 itrigger, 5 etrigger, 6 mcontrol6, 15), `matches`, `actions`, `timing`, `chain`, `unsupported_type`, `tcontrol`, `store_data_timing`, `load_data_timing` |
| `sba` | `sizes`, `asize`, `misaligned_error` (3), `size_error` (4) |
| `[transport]` | `kind` = `model`, `jtag-model`, `remote_bitbang` (`host`, `port`, `irlen`) or `dmi_process` (`command`) |
| model only | `abstract_latency`, `sba.latency`, `ticks_per_access`, `ips`, `elf` |

`examples/debug/spike.toml` declares native Spike 1.1.1-dev. It is a reference
target, not a core default.

## Drivers

- `dmi.JtagDMI` drives a JTAG DTM: TAP reset, DTMCS, pipelined DMI scans,
  sticky-busy clear with dmireset and a bounded idle increase. It runs over
  `dmi.SocketJtag` (remote_bitbang, batched TCK) or `jtag.InProcessJtag`.
- `dmi.RemoteDMI(host, port)` is `JtagDMI` over remote_bitbang.
- `dmi.BusDMI` drives a DMI bus object directly, with busy retry.
- `dmi.ProcessBus` is a core adapter's simulated DMI bus over the C1 line
  protocol (`docs/PLATFORM_CONTRACTS.md`, "C1 debug transport").
- `jtag.DTM` is the reference JTAG DTM (IEEE 1149.1 TAP, IDCODE, DTMCS, DMI,
  BYPASS, request latency, sticky busy, dmireset, dmihardreset) over any DMI bus.
- `dm.DebugModule` is the reference Debug Module with `hart.Hart` (RV I+M,
  Zicsr, traps, Debug Mode, a few compressed forms) and `triggers.TriggerUnit`.

## Compliance campaign

```sh
rvw debug suite --profile rvw-debug.toml --out /tmp/debug-results
rvw debug suite --profile examples/debug/spike.toml --port 9824 --out /tmp/spike-debug
rvw debug suite --list
```

Each check drives the target only through DMI and asserts one spec rule. It
also records observations. For a non-model target, the runner repeats each check
on a fresh reference model built from the same profile. Different observations
fail the check. A check the reference cannot pass is inconclusive. Timing
checks (busy collisions) skip the comparison. Results are C3 in
`OUT/results.json`. Exit 0 means all tests passed, 1 a failure, 3 inconclusive
or no checks.

| Group | Rules |
|---|---|
| `dm` (#127) | dmactive reset, version, HARTSELLEN, hart enumeration and nonexistent harts, halt, resume, resumereq with haltreq, unavailable harts, ndmreset and havereset, reset-halt (cause 5 at the reset vector), hartreset, haltsum0, independent multi-hart halt, hart-array mask, halt groups (cause 6), and an independent observer: memory written by a running hart stops changing while halted |
| `abs`, `pb` (#153) | GPR/CSR round trip, x0, 32-bit reads, unsupported regno/size/cmdtype, sticky cmderr and W1C, cmderr 4 on a running hart, postincrement with autoexec, resume at dpc, busy collision (cmderr 1), Access Memory sizes and postincrement, cross-checks between Access Memory and the program buffer, Quick Access, program-buffer execution, exceptions (cmderr 3; mepc, mcause, dpc and dcsr.cause unchanged), ebreak end, autoexecprogbuf, fence.i on rewritten code |
| `dbg` | dcsr debugver/prv/cause, ebreak in M/S/U with ebreakm/s/u on and off (Debug Mode entry or breakpoint exception, MPP), dcsr.prv switch, step (cause 4), step over a trap, step over ebreak, stepie, dret and dpc illegal outside Debug Mode |
| `trig` (#144) | enumeration and tinfo, WARL type/action/vs-vu, dmode protection from M-mode, execute matches for every declared match type, hit, load/store address (before), load/store data at the declared timing, privilege filters, chains, mcontrol timing=1, icount, etrigger, itrigger, action 0 in M (tcontrol.mte) and in U, mte gating, no firing in Debug Mode |
| `sba` (#156) | capabilities, every size with an independent read-back path, autoincrement, readonaddr/readondata, alignment, unsupported size, error, read-only and powered-off regions with declared sberror, errors block new accesses, sbbusyerror, accesses while the hart runs (SBA sees hart stores; the hart sees an SBA store) |

A check writes code into `scratch`, sets dpc, resumes and waits for a halt. Use a
disposable simulation. The campaign changes GPRs, CSRs, triggers and scratch memory.

## JTAG TAP and DTM checks

```sh
rvw debug tap --port 9824 --idcode 0xdeadbeef --out /tmp/tap-results
```

The checks drive raw TMS/TDI (#133): five TMS=1 cycles reset the TAP from every
one of the 16 states, IR capture is `01`, IDCODE loads after reset, BYPASS adds one
bit of delay, DTMCS fields, DMI read status, a Pause-DR mid-scan, sticky busy with
zero Run-Test/Idle cycles, dmireset and dmihardreset. A DTM that never reports busy
gives `inconclusive` for the busy check.

## remote_bitbang server

```sh
rvw debug serve --profile rvw-debug.toml --port 9824 --dtm-latency 2
```

The server wraps the reference DTM around the reference Debug Module, or around
a `dmi_process` adapter bus. OpenOCD attaches with `adapter driver remote_bitbang`.
A model hart keeps running between JTAG accesses (`--ticks-per-ms`).
`--port-file` records the port. `--duration` stops the server.

## OpenOCD and GDB interoperability

```sh
rvw debug interop --profile rvw-debug.toml --elf interop.elf --out /tmp/interop
rvw debug interop --port 9824 --elf interop.elf --reset-pc 0x1000 --out /tmp/interop
```

GDB starts OpenOCD through a pipe (`gdb_port pipe`). OpenOCD connects to the
remote_bitbang target: a running simulation, or the reference model that
`--profile` serves. A GDB Python script (`interop_gdb.py`) checks each operation
by its effect (#161):

| Check | Effect checked |
|---|---|
| `load` | the first word at `_start` equals the ELF file bytes |
| `register_write`, `memory_write` | values read back after the caches are flushed |
| `breakpoint`, `hardware_breakpoint` | the hart stops at `target`, and `counter` advanced by one loop iteration |
| `stepi`, `stepi_jump` | pc advances by one instruction, the register effect is visible, and the jump goes to `loop` |
| `watchpoint` | the hart stops after the store, and `counter` advanced by one |
| `reset_halt` | with `--reset-pc` (or a profile with resethaltreq), pc after `monitor reset halt` |

The ELF must define `_start`, `loop`, `target` and a 32-bit `counter`
(`rvw/tests/fixtures/debug/interop.S`). C3 results (`debug-interop`) record the
GDB and OpenOCD versions in `clients`. A connection without these effects is not
a pass. A GDB error belongs to the first check it did not reach. Unreached checks
are inconclusive.

Measured: OpenOCD 0.12.0+dev-00519 with GDB 18.1 passes every check against the
reference model. Against Spike, hardware breakpoints and watchpoints fail:
Spike resets each trigger to `tdata1.type` 15, and this OpenOCD skips type-15
triggers ("Couldn't find an available hardware trigger"). The other checks pass.

## Spike findings

The campaign ran against native Spike 1.1.1-dev (source revision checked:
`41b3525938644fc517cbb7d7d6cd3f32394113b3`) with `examples/debug/spike.toml`.
Spike passes the TAP campaign and most DM checks. The profile records these
Spike choices: Debug 0.13.2, no resethaltreq, no Access Register postincrement
(the bit is ignored, not refused), match types 0 to 5 only, no tcontrol,
mcontrol timing 0 only, store-data triggers before the store, SBA misaligned
error 2 and unsupported-size error 3. Spike skips two checks with reasons:
it keeps data0 when dmactive is cleared, and it has no haltsum0. Spike does not
implement dcsr.stepie and takes pending interrupts while stepping; the stepie
check reports unsupported because the bit reads 0.

## OpenOCD reference campaign

The selected profile is Debug 0.13.2, one RV64 machine-mode hart, five-bit
JTAG IR, abstract GPR/CSR access, and one `mcontrol` execute trigger.
The test changes x8, DPC, and trigger slot zero. Use a disposable simulation.
The fixture entry is `0x80000000`. This is a test profile, not a core default.

Provide an OpenOCD config that selects `remote_bitbang`, declares the TAP
and RISC-V target, disables listening servers, and calls `init`.
Start the simulator before this command. The target remains caller-owned.

```sh
rvw debug openocd --config /absolute/path/sim.cfg --log /tmp/debug.log
```

The campaign checks halted/running DM status, a separate DCSR entry cause,
abstract GPR round-trip, unsupported-command errors, sticky error clearing,
and execute-trigger entry cause and DPC. The report lists each completed check.
A missing completion marker or timeout gives `inconclusive` (exit 3).
A complete failed campaign gives exit 1. A complete passing campaign gives exit 0.
The log retains OpenOCD diagnostics. Missing tools cannot earn a pass.

`dmi.RemoteDMI` is a separate native remote_bitbang client. It resets the TAP,
reads DTMCS, discovers `abits` and idle cycles, and handles pipelined DMI requests.
It clears sticky busy and retries with a bounded idle increase. Reserved or
failed responses raise an error. Persistent busy raises a timeout.
It supports one TAP. It does not open a physical adapter.

## E-Trace

Reuse the upstream baseline decoder. Its source identifies the algorithm as
1.1.3-Frozen. The pin is `ffb6bb721f3de4e8ed9ee6d5acd52dd90df34670` from
[riscv-trace-spec](https://github.com/riscv-non-isa/riscv-trace-spec/tree/ffb6bb721f3de4e8ed9ee6d5acd52dd90df34670/referenceFlow).
This profile does not claim all ratified E-Trace options.

```sh
git clone https://github.com/riscv-non-isa/riscv-trace-spec.git /tmp/etrace-reference
git -C /tmp/etrace-reference checkout ffb6bb721f3de4e8ed9ee6d5acd52dd90df34670
rvw debug ingress --rvfi /tmp/run/rvfi.jsonl --out /tmp/encoder_input
rvw debug etrace --reference /tmp/etrace-reference \
  --packets /tmp/capture.te_inst_raw \
  --static-config /tmp/encoder.scf --user-config /tmp/decoder.ucf \
  --toolchain /path/to/riscv-toolchain \
  --rvfi /tmp/run/rvfi.jsonl --out /tmp/trace-result.json
```

Use the upstream `i_template.scf` and `i_template.ucf` as config templates.
Set `object-files` to absolute ELF paths in the user config. Set parameters to
the encoder configuration. The toolchain must contain native
`bin/riscv64-unknown-elf-objdump`. The decoder scripts must match the clean pin.
There is no automatic download or use of bundled Linux executables.

Input is upstream `te_inst` CSV or its `.te_inst_raw` packet framing.
Raw packets also pass through the pinned deserializer. The decoder receives
packets, ELF code and configuration. It does not receive expected PCs.
The wrapper compares the exact reconstructed PC sequence with validated C2
retirement records. Use `rvw cosim check` separately to check C2 state with Spike.

`flow_match` means equal PC sequences (exit 0). It does not mean equal register
or memory state. A sequence difference gives `mismatch` (exit 1). Empty data,
a missing passing C2 end, a missing trace-disabled support packet, malformed
packets, or encoder trace loss gives `inconclusive` (exit 3). `--loss` marks
external packet loss or overflow. A lost window stays unknown. This tool does
not certify recovery after a later sync packet. Result JSON includes packet,
ELF and config hashes and the decoder revision.

The ingress adapter exports one retirement per row for machine mode without
traps. It handles conditional branches and indirect jumps, including compressed
forms. It rejects unknown instructions, trap returns, traps and other privilege
modes. It does not turn retirement data into DUT encoder evidence.

## E-Trace flow with traps, loss and filters

`rvw debug etrace-check` builds the expected stream from C2 with the pinned
reference encoder. It then checks an encoder capture (#168):

```sh
rvw debug etrace-check --reference /tmp/etrace-reference --rvfi run/rvfi.jsonl \
  --static-config enc.scf --user-config dec.ucf --toolchain /path/to/toolchain \
  --packets capture.te_inst_raw [--filter filter.toml] [--loss-at N] --out /tmp/etrace
```

- Ingress covers exceptions, interrupts, trap returns and privilege changes. A
  C2 trap row needs its trap event cause. An exception is an exception-only entry
  at the trapping pc (the instruction does not retire). An interrupt is an
  exception-only entry at the interrupted pc. xRET is reported as itype 6,
  because the pinned baseline encoder treats only itype 6 as an uninferable
  discontinuity with `itype_width_p=3`, and its decoder treats xRET as uninferable.
- `packets` compares the capture with the reference stream field by field. A packet
  difference can leave the flow equal; for example, the outcome of a branch just
  before an exception is never observed. The flow verdict comes from decoding.
- Decoding splits the stream at known gaps (`--loss-at`) and at trace-lost support
  packets (qual_status 2) (#172). After a gap, packets are skipped until a sync
  start (format 3, subformat 0). Each segment gets the stream's support packet
  first, and a trace-ended support packet if a gap cut it. The decoder reports
  nothing after the last packet of a segment. Each decoded segment must match C2
  in order. Lost spans are `unknown` windows, never observed execution.
- `--filter` (TOML: `privileges`, `ranges`, `exclude`, `start`, `stop`) selects
  the qualified instructions (#195). The expected stream is one reference encode
  per qualified window. A decoded pc or a sync address from unqualified execution
  gives `leak`.

Status: `flow_match` (exit 0), `mismatch` or `leak` (exit 1), `partial_match`
(every observed window matches, some windows are unknown; exit 3), `no_checks`
without `--packets` (exit 3), `inconclusive` (exit 3). The command writes
`result.json` and `expected.te_inst`.

`rvw debug etrace-loss` damages the reference stream (or `--packets`) with each
fault: `drop`, `overflow` (a trace-lost support packet), `wrap` (a circular buffer
lost the start) and `truncate`, at sampled positions (`--at`). A test passes when
every observed window matches C2 and the lost span is reported as unknown. Results
are C3 (`etrace-loss`). Resynchronization at trap syncs (subformat 1) is not used.

## N-Trace

N-Trace support is separate from E-Trace (#194). An E-Trace result never counts
as N-Trace support. `ntrace.py` holds the codec `rvw-ntrace/1`: a reference
encoder from C2, MDO/MSEO byte packing, and a decoder. The decoder uses the program
image from the ELF, not C2.

```sh
rvw debug ntrace-check --rvfi run/rvfi.jsonl --elf prog.elf --mode htm --sync-period 2 \
  --packets capture.ntrace [--filter filter.toml] [--loss-at N] --out /tmp/ntrace
rvw debug ntrace-loss --rvfi run/rvfi.jsonl --elf prog.elf --mode btm --sync-period 2 --out /tmp/ntrace-loss
```

- Messages: Ownership (2, privilege), DirectBranch (3), IndirectBranch (4), Error (8),
  ProgTraceSync (9), ResourceFull (27, history or ICNT overflow), IndirectBranchHist
  (28), ProgTraceCorrelation (33, trace stop with ICNT and history). Bytes carry six
  MDO bits and two MSEO bits. Variable fields end on a byte boundary. Sync messages
  carry full halfword addresses; other messages carry the XOR with the last address.
- Modes: `btm` (a message for every taken direct branch and jump) and `htm` (branch
  history; a message for each indirect jump and trap). Traps use BTYPE 1.
  `--sync-period N` adds a periodic ProgTraceSync after N address messages.
- The SYNC, EVCODE, ETYPE, RCODE and BTYPE values are profile parameters with rvw
  defaults. Check them against the encoder documentation before a conformance claim.
- Decoding stops at Error messages, known gaps (`--loss-at`, message index) and
  decode failures. It resumes only at a ProgTraceSync. Windows and verdicts are
  the same as for E-Trace. A capture without its stop message is not a full match.
  A message dropped without a gap marker gives `mismatch`.
- `ntrace-loss` drops messages, replaces them with Error (overflow), discards the
  start (wrap) or cuts the end, at positions that have a later sync point.

## Vendor trace adapters

A vendor adapter (`rvw.trace-adapter/1`) configures the N-Trace codec for one
encoder (#207). It must cite the vendor `specification`, state its `license`, and
give known packet `vectors` (bytes and the messages they encode). The adapter is
used only when every vector unpacks to its messages and packs back to its bytes.
An adapter without vectors is refused: a vendor name is not evidence of format
compatibility.

```sh
rvw debug trace-adapter examples/trace/nexus-htm-template.toml
rvw debug ntrace-check --adapter my-encoder.toml --rvfi ... --elf ... --packets ... --out ...
```

`examples/trace/nexus-htm-template.toml` is a template. Its vectors come from the rvw
codec, not from a vendor. No SiFive or Andes adapter is bundled: this repository has
no vendor packet vectors with a usable license. Add one from the vendor
documentation with its vectors.

## Native validation

```sh
RVW_ETRACE_REFERENCE=/tmp/etrace-reference \
  nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_debug_spec.py -q
```

Optional tools are native Spike, OpenOCD, RISC-V GCC and objdump. Missing tools
skip their native checks. Set `RISCV_TOOLCHAIN` if its prefix is not the local
Homebrew default. The tests compile small assembly fixtures. They start bounded
Spike processes and stop their process groups on exit. The transport tests use
normal and delayed DMI. The OpenOCD test checks the full selected campaign.
The trace test executes a bounded branch/jump program with Spike, exports its
ingress, runs the reference encoder, and decodes both CSV and raw streams.
Negative tests remove the final support packet, truncate raw data, and inject
trace-loss status. These are reference streams, not RTL encoder captures.

## Core hooks and remaining work

A core adapter exposes either a JTAG DTM through remote_bitbang or a DMI bus
through the `dmi_process` line protocol. It declares its options in a debug
profile. No core adapter in this repository implements either hook yet.

Open items:

- #127: the independent observer uses memory effects only; a C2-trace observer is not added.
- #133: no RTL DMI adapter exists yet; physical transports are out of scope.
- #144: virtualization (vs/vu with H), textra/tdata3, size matching and NMI itrigger are not tested.
- #153: abstract FPR access and relaxedpriv are not tested.
- #156: concurrent-traffic ordering beyond visibility is not tested.
- #168: context changes (no C2 context field) and options beyond the baseline encoder are not tested.
- #172: recovery at trap syncs and DUT overflow markers other than qual_status 2 are not used.
- #195: authentication controls and encoder-side trigger inputs are not modelled.
- #194: timestamps, multiple sources (SRC), data trace and repeat-branch messages are not modelled; no RTL N-Trace encoder capture exists yet.
- #207: no vendor adapter with vendor vectors is bundled.

## Decisions and sources

The reference model is written from the specification text. It is used to
validate the campaigns (every check passes on it, and seeded model bugs make the
matching checks fail) and as the comparison reference. It is not an ISA
simulator. Use Spike for ISA conformance.
Reuse the [OpenOCD RISC-V client](https://openocd.org/doc-release/html/Architecture-and-Core-Commands.html)
and [Spike remote JTAG support](https://github.com/riscv-software-src/riscv-isa-sim#debugging-with-gdb).
The debug profile follows [Debug 0.13.2](https://github.com/riscv/riscv-debug-spec/releases/tag/0.13.2).
Do not infer Debug 1.0 or full Sdtrig support from this profile.
Keep core signal names and configs outside generic code. Do not change core RTL.
