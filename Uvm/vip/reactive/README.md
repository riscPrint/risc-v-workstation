# Reactive APB and AHB qualification

These small RTL managers issue one read from zero-initialized memory.
The Python cocotb subordinate drives real response pins with seeded wait
states. The good run must return zero. The bad subordinate changes the
read data and must produce the expected `APB_REACTIVE_DATA` or
`AHB_REACTIVE_DATA` diagnostic. Seed 17 selects the address and waits.

Run from the repository root with a new output directory:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/vip/reactive/smoke.py --protocol apb --out /tmp/apb-reactive-new
nice -n 10 rvw/.venv/bin/python Uvm/vip/reactive/smoke.py --protocol ahb --out /tmp/ahb-reactive-new
```

The runner uses Icarus and cocotb 2.0.1. It checks results XML and refuses
a campaign longer than one minute. No UVM runtime is built. This evidence
covers one read and seeded waits. Writes, byte lanes, error responses,
reset during a transaction and sustained pipelining remain separate.
