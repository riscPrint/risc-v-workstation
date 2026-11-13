# Live VexRiscv pyuvm environment

This project binding connects `LiveCpuEnvironment` to the simple instruction
and data buses of `examples/vexriscv` VexTop. Both ports use its shared byte
memory with seeded response delays. The scoreboard steps independent Spike
once per live retirement. A pass requires a full-word `tohost=1` retirement.
A matching prefix cannot pass. A failed program or watchdog stops the test.

Install `rvw[cocotb]` and pyuvm 4. Build the matched Spike shim with
`Cosim/build.sh`. Generate VexTop RTL from the project adapter under the
a private `vex-uvm` lock and the `sbt` lock, or copy the generated `VexTop.v` from that adapter to
this folder. Generated RTL is ignored by Git. Do not change the core.
Use the existing RV32IM ISA ELFs built by the VexRiscv project.

From the workstation checkout, with Verilator on PATH:

```sh
export RVW_CPU_SHIM="$PWD/Cosim/build/librvw_spike.so"
export RVW_CPU_ELF=/absolute/path/to/rv32ui-p-add
scripts/with-lock.sh vex-uvm nice -n 10 rvw/.venv/bin/rvw regress cocotb \
 Uvm/examples/vexriscv/bench.json --out /tmp/vex-live-add --timeout 120 --json
```

Repeat with other ISA ELFs and new output directories. Set `RVW_VEX_SEED`
to choose memory timing. `--seed` controls the simulator seed separately.
Set `RVW_VEX_CORRUPT=1` for a negative run. It changes the sixth retirement's
next PC before comparison. That run must fail with `SPIKE_MISMATCH:pc_next`.

`bindings.json` maps the project's RVFI pins. The runner writes C3 through
the cocotb adapter. `cpu-checks.json` records actual comparisons and observed
coverage only after the final store passes Spike. `spike-capture-PROGRAM` retains
the captured reference inputs. C3 source identity remains incomplete.
This example does not earn C4 acceptance.

The profile uses scalar RV32IM retirements, RAM and M-mode. It supplies optional seeded interrupt stimulus. It supplies
no debug stimulus. The selected VexTop has no debug unit.
Full interrupt qualification, debug checks and full ISA qualification remain open. The RAM-only binding reports no data faults.
It does not qualify access-fault behavior.

Use the current generated RTL directory recorded in a C1 `result.json`
`details.rtl_dir` entry. An old generated VexTop can have different
privilege modes from the selected platform. Do not mix those configurations.

When `RVW_CPU_ELF` names `rv32ui-p-add`, the test also runs adjacent
`rv32ui-p-beq`, `rv32ui-p-lw`, `rv32ui-p-sw`, `rv32ui-p-jal` and
`rv32ui-p-xor` ELFs in the same native build. Each test resets
the DUT and creates a new independent reference. Missing ELFs fail explicitly.
Per-program `cpu-checks-PROGRAM.json` files keep the actual comparison counts.

The wrapper observes separate trap pulses. It steps Spike independently and
checks cause and tval before the next retirement. This covers synchronous
trap synchronization in ISA bootstrap code. `CpuEvents` also supplies a
requested-IRQ check and independent debug halt-state comparison. Those API
checks have unit tests. They do not qualify architectural IRQ/debug behavior
on this core. The optional event program below drives interrupts. It drives no debug requests.

## Native results on 2026-11-13

Verilator 5.049, cocotb 2.1.0 and pyuvm ran the live M-only binding with
memory seed 1. Each program reset the RTL and used a fresh Spike instance.
Each program reached its checked `tohost=1` store and checked four separate
trap events against Spike.

| ISA program | Checked retirements | Cycles |
|---|---:|---:|
| add | 504 | 1986 |
| beq | 330 | 1415 |
| lw | 322 | 1250 |
| sw | 553 | 2178 |
| jal | 94 | 407 |
| xor | 526 | 2068 |

All six PC-corruption runs failed with `SPIKE_MISMATCH:pc_next`. None wrote
a completion summary. The opt-in native pytest returned 2 passed, 0 skipped.
The test checks separate capture paths, trap counts and per-program summaries.
The private VexRiscv copy was at `a62c145aa042a5de874344e0a7683bd7c8c8c870`.
RTL SHA-256 was
`80b1dfec5f3dde68a490dbf05cbee620b4ae3cc4e627ffff045d1a25e0856159`.
The rebuilt ABI 6 shim matched the current source. An older shim was refused.

Local evidence is under
`$VEXRISCV/uvm-runs/native-pytest/`.
The runs used the private `vex-uvm` lock. The binding has no supervisor
interrupt port because the selected RTL is M-only. These six tests do not
establish full ISA coverage, interrupt/debug support or C4 acceptance.

## Native interrupt and CSR sequences

```sh
Uvm/examples/vexriscv/build-events.sh /tmp/vex-events-new
RVW_VEX_EVENTS_DIR=/tmp/vex-events-new scripts/with-lock.sh vex-uvm nice -n 10 \
 rvw/.venv/bin/python -m pytest rvw/tests/test_uvm_events_native.py -q
```

Set `RVW_CPU_SHIM` and generate the matching VexTop RTL first. Put the
RISC-V compiler on PATH. Use `RISCV_PREFIX` for another compiler prefix.
The build refuses an existing output directory.

The interrupt program enables MSIP, MTIP and MEIP, sets an M-mode handler,
then waits for eight interrupts. The environment chooses request causes
and gaps from its seed. It holds each request until a real trap pulse.
`CpuEvents` verifies the cause was requested and checks cause/tval with
independently stepped Spike. The handler executes `mret`. Every retirement
also passes the ordinary Spike scoreboard. Completion requires eight
interrupt checks and a checked `tohost=1` store.

The CSR program comes from the standard catalog selection in `csr.json`.
It initializes unknown-reset `mscratch`, reads it, and tests zero, all ones,
walking ones and seeded random writes with readback. It restores zero.
The native collector records actual CSR retirements. `CsrQualification`
then checks those responses against the independent catalog model. It also
checks each instruction's CSR address, operation and source write data.
Spike checks the complete instruction stream independently.
Only present, permitted M-mode CSR operations use this collector. Denied
accesses require a separate trap collector and are refused during planning.

Native results on 2026-11-13 with Verilator 5.049:

- IRQ seeds 1 and 3: eight synchronized interrupt events per run.
- CSR seed 1: 88 catalog checks and 145 Spike retirement comparisons.
- Opt-in event tests: 3 passed, 0 skipped.

The selected M-only VexTop has no debug unit or debug request port.
Native random debug-request tests cannot run on this configuration.
A debug-enabled project configuration and matching architectural reference
are still required. These IRQ and CSR runs do not establish debug support,
all CSR semantics or C4 acceptance.
