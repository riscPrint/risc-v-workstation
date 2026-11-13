# Composed block device

The device has eight volatile 512-byte sectors. It is a verification block
store. It does not implement SD signalling, a card controller or persistence.
An independent bus master drives the composer-generated simple-bus ingress
and APB fabric. No CPU instructions execute.

```sh
source /path/to/spinal-boom/env.sh
rvw/.venv/bin/python SpinalSoc/examples/block/run.py --out SpinalSoc/out/block-run
```

The helper uses `vex-soc` and `sbt-soc`, a private generated source directory
and Verilator assertions. It needs no external CPU checkout. The directed test
writes one full sector, reads it back, checks zero data in another sector,
checks sector isolation, transfer completion, IRQ, abort and status clear.
It also rejects out-of-range LBA, inactive DATA, incorrect DATA direction,
a changed active LBA and an overlapping command.

On 2026-11-13 the isolated helper passed with Verilator assertions at seed 47.
The directed test compared 257 read words after 128 patterned writes. The sbt
compile/simulation step took 34 seconds. This is development evidence for the
listed register and sector-transfer cases.
