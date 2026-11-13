# Native instruction and IRQ reduction

This recipe runs `rvw reduce` on captured VexRiscv RTL with Arcilator. It uses
the existing instruction and IRQ stream reducers. Each candidate runs the
whole core in a new native process. Seed 7 controls instruction and data bus
ready stalls. Bus responses have one cycle of delay. The program and IRQ
schedule provide deliberate failures. They do not identify a new core defect.

Set the JDK, CIRCT and RISC-V compiler paths. Set `RVW_HOME`, `RVW_PYTHON`,
`VEXRISCV` and `RVW_VEX_LOCK=vex-NAME` for the private worker copy and lock.
Use a source capture without submodules. The measured source copy came from
VexRiscv `a62c145aa042a5de874344e0a7683bd7c8c8c870`. Its unused
`src/test/resources/VexRiscvRegressionData` gitlink was removed in a private
local commit. `RVW_SOURCE_PIN` records that upstream revision. The C8 report
records the actual local revision and source fingerprint.

Prepare a new directory outside the workstation checkout:

```sh
nice -n 10 rvw/.venv/bin/python examples/vexriscv/rvw/reduction/prepare.py \
  --rtl /path/to/VexTop.v --out /path/to/new-reduction
```

Preparation copies the RTL, port map and project adapter. It builds both
RV32 programs. Its local ignore rules keep the required port map in C8 when
the output sits in a private VexRiscv copy that ignores JSON files.
Set `RVW_CORE_CONFIG=/path/to/new-reduction/harness/debug.toml`.
Run each original case:

```sh
/path/to/new-reduction/harness/run.sh run \
  --elf /path/to/new-reduction/instructions.elf \
  --out /path/to/new-reduction/instruction-fail
/path/to/new-reduction/harness/run.sh run \
  --elf /path/to/new-reduction/interrupts.elf \
  --irq-schedule 1:0x0,80:0x8,100:0x0,120:0x8,140:0x0,160:0x8,180:0x0 \
  --out /path/to/new-reduction/irq-fail
```

Exit code 1 and C1 `fail:1` are expected. A timeout or missing C1 is not a
reproduction. Run each reduction under the same private lock:

```sh
RVW_NO_LOCK=1 RVW_NO_RUN_MANY=1 scripts/with-lock.sh vex-NAME nice -n 10 \
  rvw/.venv/bin/rvw reduce /path/to/new-reduction/instruction-fail \
  --out /path/to/new-reduction/instruction-reduced --modes instructions \
  --instruction-symbol fault_region --budget 64 --timeout 60 --json
RVW_NO_LOCK=1 RVW_NO_RUN_MANY=1 scripts/with-lock.sh vex-NAME nice -n 10 \
  rvw/.venv/bin/rvw reduce /path/to/new-reduction/irq-fail \
  --out /path/to/new-reduction/irq-reduced --modes irq \
  --budget 64 --timeout 60 --json
```

`RVW_NO_LOCK=1` suppresses an extra generic core-name lock. Use it only with
the outer private lock. The project launcher uses that same private lock.
C8 freezes the ELF, source and adapter assets. C4 reuse remains disabled.
The adapter accepts an output directory that the debug tool already created.
Its native model writes below `native-run/`.

## Measured result

On 2026-11-13, both reductions completed with seven conclusive native trials.
[measurements.json](measurements.json) records report, ELF and C2 hashes,
source identity, trial times and outcomes. `summarize.py` validates each trial's
C1 and complete C2 with the shared parser before it writes this sample.

| Stream | Original | Retained | Native reduction time | Completion |
|---|---:|---:|---:|---|
| `fault_region` replaceable slots | 8 | 1, index 3 | 9.6 s | `one_minimal` |
| Removable IRQ events | 6 | 1, index 5 | 10.9 s | `one_minimal` |

The instruction result keeps `addi a0,a0,1`. Seven slots become 32-bit NOPs.
ELF size and code addresses stay fixed. The result still retires 15
instructions and fails at cycle 40. It is not a one-instruction whole program.
Removing the final retained slot gives a native pass at cycle 41.

The IRQ result keeps `1:0x0,160:0x8`. The first event is required by the IRQ
stream format and is not counted among removable events. The assertion at
cycle 160 runs concurrently with the program. It causes machine software
interrupt `0x80000003`. The handler writes failure at cycle 180. The quiet
schedule `1:0x0` passes at cycle 1576. No inconclusive or timed-out candidate
was used to establish local minimality. Each best result also passed a fresh
failure confirmation run. No global minimum is claimed.

## Trace and input limits

IRQ levels use standard `mip` bit positions: software `0x8`, timer `0x80` and
machine external `0x800`. Supervisor external `0x200` is available only when
the captured port map has `externalInterruptS`. Other bits are refused before
a native build. Events are applied before the named cycle and remain active
until replaced. C2 records level changes and actual trap observations. Trap
records use the canonical boolean `intr` field. Every completed Python probe
trace is parsed before C1 is published. Headers include `config` and `elf`.
The live checkpoint probe includes those fields too.

Native controls passed with the full and empty instruction regions and with
asserted and quiet IRQ schedules. General multi-hart stimulus, reordered
schedules, device transaction reduction and unknown upstream failures were
not run. This recipe provides the real instruction and concurrent IRQ piece
of #152. Broader stimulus reduction remains separate work.
