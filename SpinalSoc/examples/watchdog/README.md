# Composed watchdog test

This example uses `VerificationCore`, the simple-bus ingress, the generated
APB fabric and the watchdog peripheral. It does not execute CPU instructions.
The register map and composer file are project inputs. The watchdog IRQ uses
cause 11. The exported reset request is observed by the test. It does not
reset the testbench or core automatically.

```sh
source /path/to/spinal-boom/env.sh
rvw/.venv/bin/python SpinalSoc/examples/watchdog/run.py --out SpinalSoc/out/watchdog-run
```

Run from the workstation root. The helper uses private `vex-soc` and
`sbt-soc` locks. It selects only its generated source directory. It does not
require or build an external CPU. Read `native.log` for the native result.

The directed test checks disabled reset state, countdown, incorrect service
key, correct service reload, expiry, IRQ routing, reset request, status clear
and zero-reload saturation. This is a bounded peripheral/fabric test. It does
not qualify watchdog clock independence or a platform reset sequence.

On 2026-11-13 the documented helper compiled the isolated composition and
passed the directed Verilator run at seed 43 with `--assert`. The sbt compile
and simulation step took 49 seconds. The map and release hygiene set had
51 passing tests. This is development evidence for the listed cases.
