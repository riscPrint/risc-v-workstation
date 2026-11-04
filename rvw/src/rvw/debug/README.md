# Debug transport and instruction trace

`rvw debug` checks simulated debug targets and baseline E-Trace streams.
OpenOCD is the debug client. Spike supplies the reference JTAG DTM and Debug
Module. A reference-model pass does not prove a core implementation.

## Debug campaign

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

## Proposed core hooks and remaining work

A core adapter must expose a simulated DMI request/response bus or a JTAG DTM
through remote_bitbang. It must declare the DM version, harts, abstract command
options and triggers. It must supply an independent hart-state observer.
An encoder adapter must export actual packet bytes and its static/runtime
configuration, plus independent C2 retirement data from the same run.
These are proposals. This change does not add or test core hooks.

Open acceptance items remain:

- #127: unavailable harts, reset entry, multi-hart groups and core-state observers.
- #133: a declared RTL DMI bus adapter, full TAP/busy/reset fault injection and core validation.
- #144: load/store, count/chained triggers, privilege, virtualization and WARL campaigns.
- #168: RTL encoder ingress, independent exception/context streams and wider options.
- #172: overflow, dropped packets, buffer wrap and certified sync recovery windows.
- #194: a separate versioned N-Trace decoder and campaign. E-Trace cannot count as N-Trace.

## Decisions and sources

Reuse the [OpenOCD RISC-V client](https://openocd.org/doc-release/html/Architecture-and-Core-Commands.html)
and [Spike remote JTAG support](https://github.com/riscv-software-src/riscv-isa-sim#debugging-with-gdb).
The debug profile follows [Debug 0.13.2](https://github.com/riscv/riscv-debug-spec/releases/tag/0.13.2).
Do not infer Debug 1.0 or full Sdtrig support from this profile.
Keep core signal names and configs outside generic code. Do not change core RTL.
