# PicoRV32 architectural-state monitor

Use pinned PicoRV32 `ef203c2b0a3fb793280f5114941416c425c5b461` outside
this repository. Run these commands with the workstation environment loaded:

```sh
rvw/.venv/bin/python examples/picorv32/formal/prepare.py \
  --source "$PICORV32" --riscv-formal "$RISCV_FORMAL" --out "$CAPTURE"
rvw/.venv/bin/rvw formal state-generate "$CAPTURE/state-map.json" --out "$MONITOR"
rvw/.venv/bin/python examples/picorv32/formal/compare.py --capture "$CAPTURE"
```

`prepare.py` checks the revision and clean source. It captures the source and
adds retirement-aligned register snapshots. It does not edit PicoRV32. The map
uses the captured snapshots, instruction events and memory transactions. It
never maps native RVFI outputs back into the generated monitor. The example
uses RV32I, no IRQ, no compressed instructions, no PCPI and zero register reset
state. Native RVFI remains in the captured source for comparison only.
The generated monitor supports the core's active-low reset and halt output.

Run the comparison under a private lock and `nice -n 10`:

```sh
cd "$CAPTURE"
iverilog -g2012 -s tb -o sim miter.sv monitor.sv tb.sv
vvp sim +program=0
vvp sim +program=1
vvp sim +program=2
sby -f miter.sby check
sby -f miter.sby cover
```

The three programs cover dependent arithmetic, memory operations, shifts and
branches. Each simulation compares all RVFI fields for 30 retirements.
Formal compares validity on every active cycle and all fields on a valid cycle.
The monitor also checks the architectural register frame. Reachability asks
for a fourth retirement. Source reset and memory-service restrictions remain
visible in the generated SBY model.

## Measured outcomes

Native run on 2026-11-13 used Icarus, Yosys, SBY and Bitwuzla.

| Check | Outcome |
| --- | --- |
| Map exposure and monitor generation | generated; not a proof |
| Arithmetic, memory and branch simulation | 3 programs, 30 retirements each, no stream mismatch |
| Full bounded stream equivalence, depth 35 | FAIL at cycle 10 |
| Fourth-retirement cover | reached at cycle 18 |

The counterexample contains instruction `0xfeeff76f`, a JAL with a misaligned
target. Native RVFI retains the destination write on the trap. The architectural
monitor suppresses destination writes on a trap and detects the changed register
frame. This is an unresolved difference. The kit does not certify PicoRV32's
RVFI or the state map as equivalent. The simulation matches do not remove it.

Private evidence is stored in `pico-state-source-v1` and
`pico-state-monitor-v1` under the worker's private evidence directory. The
formal source snapshot is retained under `miter_check/src`; generated comparison
source can later differ. The source revision and hash are in `source.json`.
The native runs held `vex-conn` and used `nice -n 10`.
