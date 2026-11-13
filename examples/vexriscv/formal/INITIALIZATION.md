# Native initialization checks

The fresh RV32IM export from `NATIVE_SECURITY.md` was checked with
`formal xprop`. Inputs were defined. Reset was active for steps zero and one.
The bound was eight. The observations were `iBus_cmd_valid` and
`dBus_cmd_valid`. Native commands used `vex-equiv` and `nice -n 10`.

```sh
scripts/with-lock.sh vex-equiv nice -n 10 rvw/.venv/bin/rvw formal xprop \
  --verilog /path/to/rv32im/VexTop.v --top VexTop --clock clk --reset reset \
  --reset-cycles 2 --depth 8 --signal iBus_cmd_valid --signal dBus_cmd_valid \
  --replay icarus --timeout 90 --out /path/to/new-run --json
```

The Yosys X model found candidates for both signals at step seven.
The initial run took 29.3 seconds. The replay run took 27.7 seconds.
No cells were unencoded. No requested signal was missing.

Icarus compiled and completed both captured-source replays. Neither replay
confirmed an unknown on either observation. Each target disposition is therefore
`inconclusive`. The formal candidate status remains `fail` in the native
report. It must not be read as a confirmed four-state RTL fault.

This run does not prove that reset defines all core state. It does not explain
the difference between the formal X model and four-state replay. The separate
two-copy initialization counterexample remains in `NATIVE_SECURITY.md`.
That check uses independent binary initial states and a different observation
contract. Its result does not confirm these X candidates.

The PMP export is blocked by the two undriven signals recorded in that document.
VexiiRiscv initialization was NOT RUN. No example core earned an initialization
pass. See `initialization-results.json` for both native receipts.
