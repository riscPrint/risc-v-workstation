# Default asynchronous-reset initialization

The default RV32IM example was exported from private pinned source copies.
The core, SpinalHDL and rvls revisions are in `initialization-results.json`.
The generator revision was `3602526c`. Native builds used `sbt-equiv`
and `nice -n 10`. No core source was changed.

The export completed after supplying the launcher property required by
`VexiiTop.liveMap`. From `examples/vexiiriscv/rvw`, with `RVW_HOME`
and `VEXIIRISCV` set to the workstation and private core:

```sh
"$RVW_HOME/scripts/with-lock.sh" sbt-equiv nice -n 10 sbt -batch \
  '++2.13.14!' \
  'set Compile / run / javaOptions += "-Driscvsim.script=/path/to/workstation/examples/vexiiriscv/rvw/run.sh"' \
  'runMain rvwvexii.SecRtl /path/to/rtl'
```

The full export retains ASYNC reset. The X observations were
`FetchCachelessPlugin_logic_bus_cmd_valid` and
`LsuCachelessPlugin_logic_bus_cmd_valid`.

## Native outcomes

- X-propagation at depth eight with two reset samples: refused asynchronous FFs.
  This flow uses a synchronous state model.
- Two-copy initialization through event-aware app BMC at 16 global samples:
  refused app attribution because the DUT already has source assertions.
- Standard event-aware BMC with all source assertions retained:
  refused reset-triggered assertions. The clock probe found reset in their
  trigger vectors. The solver did not run.

The source audit found eight assertions per core copy and no source assumptions.
The two-copy wrapper adds one initialization comparison. No assertion was
removed. No reset conversion or constant was added to obtain a pass.

## Reset-event qualification

A local experiment allowed the public reset in assertion trigger vectors.
Two native controls rejected that extension:

- `always @(posedge reset) assert(reset)` failed in the experimental BMC run.
- `always @(posedge reset) assert(!reset)` passed in that run.

Independent Icarus execution produced zero assertion errors for the first
control and two errors for the second. The experimental model therefore did
not qualify these reset-event semantics. The guard change was discarded.
The current guard still refuses both controls. Regression tests require either
that refusal or correct positive and negative native control outcomes.

The default core's initialization verdict remains inconclusive.
No native X/reset pass or core fault is claimed. A qualified model of these
asynchronous assertion events is required before this check can continue.

The guarded X-propagation attempt was:

```sh
scripts/with-lock.sh vex-equiv nice -n 10 rvw formal xprop \
  --verilog /path/to/rtl/VexiiRiscv.v --top VexiiRiscv --clock clk --reset reset \
  --reset-cycles 2 --depth 8 --timeout 90 --replay icarus \
  --signal FetchCachelessPlugin_logic_bus_cmd_valid \
  --signal LsuCachelessPlugin_logic_bus_cmd_valid --out /path/to/new-x-run
```

The combined check retains both copies' source assertions and the initialization
comparison in `initialization-pair.sv`:

```sh
scripts/with-lock.sh vex-equiv nice -n 10 rvw formal bmc \
  --verilog /path/to/rtl/VexiiRiscv.v examples/vexiiriscv/formal/initialization-pair.sv \
  --top rvw_security_pair --clock clk --reset reset --reset-cycles 2 \
  --event-model --async-reset --depth 16 --timeout 90 --out /path/to/new-event-run
```

The depth is a global-sample bound. It is not sixteen core cycles.
This command currently returns the documented trigger-model refusal.
The wrapper has no source assumptions, no architectural prefix guard and no
bus protocol assumptions. It compares the two bus-valid outputs after reset.
Independent initial architectural register values remain outside any reset
guarantee. No core fault follows from these attempted contracts.
