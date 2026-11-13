# Cacheless SMP example

This example runs two to eight RV64IMA VexiiRiscv RTL cores in Verilator.
Each core has a separate fetch bus, LSU bus, reset PC and retirement probe.
All cores use one simulation RAM. The simulation memory service implements
LR/SC reservations and the nine standard AMOs at word and doubleword widths.
It invalidates overlapping reservations when a write is accepted.

## Setup

Use a private external VexiiRiscv checkout. No core source is changed.
The pinned revision is `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
Its SpinalHDL pin is `de72faf6062206a89b445e5cc07e32ed982712c8`.
Its rvls pin is `847ce99fd2b28a5c0ccb1ec2683311cf97a9fefc`.
Use JDK 21, sbt, Verilator and RISC-V GCC.

```sh
export RVW_HOME=/path/to/risc-v-workstation
export VEXIIRISCV=/path/to/private/VexiiRiscv
export RVW_VEX_LOCK=vex-mem
# For a new checkout only:
examples/smp/rvw/bootstrap.sh
source /path/to/spinal-boom/env.sh
export PATH=/opt/homebrew/opt/riscv-gnu-toolchain/bin:$PATH
rvw/.venv/bin/python examples/smp/rvw/programs.py --suite smoke --out examples/smp/rvw/out/smoke
examples/smp/rvw/run.sh run --config smp2 \
  --elf examples/smp/rvw/out/smoke/hart-0.elf \
  --hart-images examples/smp/rvw/out/smoke/hart-images.json \
  --out examples/smp/rvw/out/smoke-run --rvfi-trace --seed 17 --json
```

The launcher takes the private `vex-mem` lock. Compilation takes the `sbt`
lock. Outputs stay in this example or the private source directory.
Select `smp3` through `smp8` and build the same number of hart images for N harts.
Each entry must equal `0x80000000 + hart * 0x20000`.
RAM spans `0x80000000` through `0x81ffffff`.
Every hart must retire a nonzero store to its own ELF `tohost` symbol.
An incomplete hart prevents a passing C1 result.

## Trace and reference scope

The upstream retirement probe produces per-hart C2/2 streams in one file.
Capture order is not a memory-order oracle. The header declares physical addresses and unavailable memory dependencies.
The project scalar binding below can add complete dependency observations to
a separate derived trace. The original trace remains unchanged. Completion
alone does not establish RVWMO correctness.

Use `programs.py --suite amo` for 72 checks per hart. Each check verifies
the returned old value and the new memory value. The matrix covers nine AMOs,
two widths and four aq/rl combinations. Use `--suite lrsc` for successful
LR/SC retries and SC-without-LR failure at both widths. These programs use
separate target words per hart. They do not check cross-hart reservations.

## Decisions and limits

SpinalSoc currently exposes a single-core APB wrapper. This example uses a
small project-owned Spinal top instead. Core buses are separate RTL ports.
Shared RAM and atomic service are simulation models, not synthesized fabric.
There are no caches and no TileLink-C channels. Cache and coherence observer
bindings are therefore absent. This example cannot qualify coherent caches.
CLINT and a seven-source machine-context PLIC are simulation models.
CPU-level PLIC claim/complete is NOT RUN. The sections below describe the
bounded IPI, HSM and cross-hart instruction visibility programs. Do not use this example as a Linux-capable SoC.
The identity is available, but complete reusable build-input capture is not
claimed. `input_complete` remains false.

## Measured results

On 2026-11-13, the three-hart smoke passed in Verilator at seed 17.
It took 86 cycles and retired 35 instructions: 11, 12 and 12 per hart.
All three C2/2 completion records report pass. The C1 instruction count equals
the validated C2 retirement count. This is simulation evidence, not hardware
qualification. Five Python tests passed. The native source build passed.
See `rvw/smoke-result.json` for the core, RTL and trace hashes.


## Ordering campaigns

`suite_programs.py` links the existing portable LR/SC, AMO and fence programs
at each hart's private reset vector. It leaves their assertions unchanged.
For example, from the workstation root:

```sh
rvw/.venv/bin/python examples/smp/rvw/suite_programs.py --suite amo --seed 17 --out examples/smp/rvw/out/amo
examples/smp/rvw/run.sh run --config smp2 --elf examples/smp/rvw/out/amo/hart-0.elf --hart-images examples/smp/rvw/out/amo/hart-images.json --out examples/smp/rvw/out/amo-run --rvfi-trace --seed 17 --json
```

At seed 17, LR/SC passed on two RTL harts: 1060 cycles and 498 retirements.
AMO passed: 18630 cycles and 8346 retirements. AMO checks 144 operand cases per
hart, including signed extrema, random operands, word sign extension and
guard bytes. Targets are private to each hart. The generated programs below
also exercise shared targets.

`litmus_programs.py TEST --out DIR` compiles one of the six pinned SB, MP and
LB tests, with and without fences. The parser checks the exact source hash.
Run each resulting hart manifest with `smp2`. Store inputs at
`rvw/out/litmus/TEST_NAME` and captures at `rvw/out/litmus/TEST_NAME-run`.
Then use the existing outcome checker:

```sh
export PATH="$RVW_HOME/rvw/.venv/bin:$PATH"
python RiscvSim/tests/ordering/litmus.py --tests /path/to/pinned/litmus-tests-riscv --herd /path/to/herd7 --herd-source /path/to/pinned/herdtools7 --dut-adapter examples/smp/rvw/litmus-outcome.py --out examples/smp/rvw/out/litmus-checked
```

Use the revisions in `RiscvSim/tests/ordering/litmus-pins.json`. Set
`RVW_SMP_LITMUS_OUT` when captures use another root. All six native captures
at seed 17 are consistent with native herd7 7.58 outcomes. Each case has one
observed outcome. This does not establish outcome coverage or ISA compliance.
The reader checks completion, ELF hashes and every retired instruction byte.

## Scalar RVWMO observations

Use `rvw memory concurrent-build` to generate per-hart inputs. Run those inputs
with `smp2`. Then bind dependencies and run the independent checker:

```sh
rvw/.venv/bin/python examples/smp/rvw/scalar_dependencies.py --trace RUN/rvfi.jsonl --out RUN/dependencies.jsonl
rvw memory axiomatic --trace RUN/dependencies.jsonl --reference INPUTS/initial.json --limit 100000
```

The binding uses the RVWMO source/destination register rules. It tracks address,
data and control dependencies per hart. It pairs LR/SC. Failed SC creates no
memory event and does not kill old register provenance. Loads and atomics do
not carry source dependencies to their destination. Unknown instructions,
faults, traps, device accesses and later resets refuse a complete binding.
The derived header records the input trace hash and binding source hash.
See the [RVWMO dependency tables](https://docs.riscv.org/reference/isa/v20260120/unpriv/rvwmo.html).

Four generated programs ran on RTL. Seed 17 used length 2. Seeds 1, 7 and 23
used length 4. Seeds 7, 17 and 23 are allowed after 6, 1 and 8 candidates.
Seed 1 remains inconclusive at 100000 candidates. The candidate limit was not
waived. These finite results do not prove general RVWMO compliance.

## Multi-hart Spike comparison

`serial2` boots both harts at `0x80000000` from one common ELF. Each hart uses
its own 8-byte slot in `tohost`. The harness serves one data operation at a
time. It waits for that operation's retirement before serving another.
This enforces the existing `serialized-retirement` cosim profile.
The concurrent `smp2` profile makes no such declaration.

```sh
rvw/.venv/bin/python examples/smp/rvw/cosim_program.py --out examples/smp/rvw/out/serial
examples/smp/rvw/run.sh run --config serial2 --elf examples/smp/rvw/out/serial/shared.elf --hart-images examples/smp/rvw/out/serial/hart-images.json --out examples/smp/rvw/out/serial-run --rvfi-trace --seed 17 --json
rvw --project examples/smp/rvw.toml cosim check --elf examples/smp/rvw/out/serial/shared.elf --trace examples/smp/rvw/out/serial-run/rvfi.jsonl --json
```

Spike matched all 38 instructions in the captured two-hart shared-memory test.
It applied zero masks and zero synchronizations. A seeded observation-bit fault
was rejected at hart 0, instruction 0, with an `rd_wdata` mismatch. This is a
negative control, not a core defect. Serialized comparison is not an RVWMO
outcome oracle. Interrupts and WFI are not qualified in `serial2`.

## Cross-hart visibility and lifecycle

`visibility_programs.py --suite fence-i-cross --out DIR` builds a writer and
an instruction receiver. The receiver executes `FENCE.I`, calls the written
code, checks its result and acknowledges completion. Both harts must pass.
The seed-17 RTL run passed in 191 cycles with 62 retirements. This is a
cacheless instruction-visibility check. There is no instruction-cache monitor.

`--suite ipi` builds a CLINT software-interrupt sender and a receiving handler.
The handler checks `mcause`, clears MSIP and acknowledges the sender.
The seed-17 run passed in 247 cycles with 74 retirements. C2 records one
software-interrupt trap and MSIP transitions from zero to eight to zero.
The adapter samples trap values before the upstream probe reports the trap.
It records actual IRQ input changes and trap events per hart.

`hsm2` adds S/U privilege with physical addresses and concurrent memory service.
Build its common test firmware with `cosim_program.py --source
examples/smp/rvw/programs/hsm.S --out DIR`. Use configuration `hsm2` for the run.
The firmware exercises selected SBI HSM start, stop and status calls. Hart 1
starts twice with distinct opaque values. The observer checks the retired
service points, actual S-mode entry PC, opaque values and IPI inputs.
The seed-17 run passed in 1431 cycles with 530 retirements. The observer
recorded two starts, two S-mode entries, one stop, one stopped state and two
IPIs. Nine separate device-model checks also passed.
This is a bounded software lifecycle test. It does not qualify all SBI calls,
clock gating, independent reset or power control.

`rvw/native-results.json`, `visibility-results.json`, `litmus-result.json`,
`random-results.json`, `ipi-result.json`, `hsm-result.json` and
`serial-cosim-result.json` hold measured evidence.
Use `summarize.py RUN...` to validate C1/C2 count and completion consistency.
