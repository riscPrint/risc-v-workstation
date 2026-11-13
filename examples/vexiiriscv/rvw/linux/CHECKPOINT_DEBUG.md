# Debug a stopped boot slice

Use the boot-slice harness from the same build that wrote the checkpoint.
Keep its frozen runtime. The harness checks the model, input, RAM, device
and host-state identities before it restores state. It refuses an older
checkpoint when an observer or harness change changes those identities.

No C2 or wave file is written by default. Set an absolute cycle window to
capture one interval after restore:

```sh
export RVW_BOOT_CLASSPATH=FROZEN_RUNTIME/classpath.txt
export RVW_BOOT_WORK=NATIVE_WORK
export RVW_BOOT_TRACE=1000000:1004096
export RVW_BOOT_WAVE=1000000:1004096
rvw/boot-slices.sh INPUTS/reset.elf INPUTS/payloads.json INPUTS/devices.json \
  WINDOW_RUN CHECKPOINT restore 1004096
```

The C2 window can cover at most 65,536 cycles. The FST window can cover at
most 4,096 cycles. Both use cumulative logical cycles. Copy the starting
checkpoint before a diagnostic run if the normal boot must resume from it.
The launcher replaces the supplied checkpoint when the slice stops.

The passive observer keeps its pending retirement, raw instruction tags
and destination write tags in RTL state. The checkpoint also keeps host
memory effects for in-flight native bus commands. The C2 fields use the
core's actual retired instruction, source values, destination value,
virtual address and privilege. Memory data comes from the accepted native
bus transaction. C2 also includes its physical address as an extra field.
The observer does not reconstruct RAM values after the instruction runs.
It refuses an unobserved destination, memory effect or raw instruction.

The observer waits for the next retirement or trap to observe `pc_next`.
The final pending retirement can be absent at a window boundary. It is not
filled with an assumed fall-through address. `order` starts at zero within
each C2 file. `absolute_order` links it to the full run. A bounded window
has no reset prefix. A normal reset-based cosim check cannot use it alone.

Set `RVW_BOOT_REFERENCE_INPUTS=1` on the reset run to keep a compact input
history for later reference replay. This option is off by default. A restore
keeps the reset-time setting. It cannot enable a missing prefix later.
The history includes device responses, counter reads, trap boundaries and external
interrupt input levels. It does not keep every retirement or RAM access.
The input records retain actual observation cycles. The checkpoint array
uses append order. Consumers group the records by their absolute retirement
boundary. It is not a standalone C2 stream.

The C2 window declares `rvw.external-interrupts/1`. Its external events
use local C2 retirement boundaries. The checkpoint uses the same evidence
fields with absolute retirement boundaries. Interrupt `taken` evidence
comes from the core trap output. The harness does not infer it from WFI.

Build a diagnostic view and bundle with the existing tools:

```sh
python rvw/linux/debug_result.py --report WINDOW_RUN/result.json \
  --checkpoint CHECKPOINT --elf INPUTS/reset.elf --out DEBUG_RUN \
  --trace WINDOW_RUN/rvfi.jsonl --wave WINDOW_RUN/wave.fst
rvw bundle DEBUG_RUN --project rvw64.toml --no-rerun --no-spinaltrace --out BUNDLE
```

The launcher saves the FST in `WINDOW_RUN/wave.fst` before another process
can reuse the native test directory. It removes the native duplicate.
The diagnostic C1 view
records `wave_cycle_origin` and `wave_time_origin`. This pair maps cumulative
logical cycles to the new process's simulator time. Its period is 11
simulator time units. The equivalent cycle-1 offset can be negative because
that earlier cycle is outside the captured wave.
Native C2 uses the zero-based pre-edge cycle index. C1 counts completed
clock edges from one. The converter shifts the wave cycle origin by one
for the C1 view. It records `boot_trace_cycle_base=0` so consumers can keep
the C2 cycle domain distinct.
The view remains inconclusive for acceptance because C1 replay is not bound.
Inspect the bundle and delete the wave and trace when they are no longer
needed. Keep only summary tables and small results outside the repository.

## Induce a timer-input hang

`timer-hang.S` writes `A`, programs `mtimecmp`, then waits for an interrupt.
Its handler writes `I` and requests power-off. The native test restores a
checkpoint before the timer expires. The control run keeps the timer input.
The diagnostic run sets `RVW_BOOT_MASK_TIMER=300:1500`. The CLINT continues
to run, but the harness masks MTIP at the core pin during that interval.
The report includes both device and driven interrupt levels.

The mask is an explicit test fault. It is outside the checkpoint identity.
The report records its interval. Removing the mask on the next restore
must allow the handler and power-off to run. This distinguishes a stopped
input from a stuck core. It does not establish Linux hang-debug coverage.

| Native checkpoint control | End cycle | Retired | Console | Result |
|---|---:|---:|---|---|
| Before timer, no C2 or wave | 300 | 14 | `A` | Bounded checkpoint |
| Normal restore | 643 | 20 | `AI` | Power-off |
| Timer pin masked after restore | 1,500 | 14 | `A` | No new retirement; device MTIP `0x80`, driven input `0` |
| Restore with mask removed | 1,543 | 20 | `AI` | Power-off |

The normal and recovered C2 windows each contain five records. The stalled
window contains zero retirement records and records its input level. The
final pending retirement is omitted when no next boundary was sampled. The requested
FST was 62,443 bytes. The bundle used the restored clock origin, included
4,044 wave signals and covered the stopped C1 cycle. The C1 view remained
inconclusive because replay is not bound. The waves and bundle wave windows
were deleted after inspection. Only small summaries remain outside the repo.

```sh
python -m pytest rvw/tests/test_boot_trace.py -q --basetemp=EXTERNAL_TEST_DIR
```

Run this command from the example directory with the native build tools
configured. The test uses the private `vex-linux` and `sbt-linux` locks
through the launcher. Its output directory must be outside the repository.
