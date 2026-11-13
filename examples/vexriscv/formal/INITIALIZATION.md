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

## Saved-candidate decision

Both saved witnesses are rejected by a new source RTL Icarus replay from
reset. No solver register values are loaded. Reset is high for two rising
edges. All external inputs retain the saved solver sequence. Both bus-valid
outputs are logged before and after every rising edge. Both outputs are
known at every post-reset sample.

| Candidate | Claimed step | Trace 0 value | Trace 1 value | Decision |
| --- | --- | --- | --- | --- |
| `iBus_cmd_valid` | 7 | 1 | 0 | Reject saved X witness |
| `dBus_cmd_valid` | 7 | 0 | 1 | Reject saved X witness |

The claimed X state is not reached by either saved input sequence in source
four-state simulation. The original formal report remains unchanged. These
replays do not establish all-input unreachability. Icarus control-flow X
optimism and the Yosys X model have different semantics. No claim of a
confirmed architectural X fault or a whole-core initialization pass follows.
The independent binary-state counterexample in `NATIVE_SECURITY.md` is a
separate contract and remains valid.

The exact benches, clock-phase logs and RTL hash are in `x-candidates/`.
The benches make no hierarchical assignments and do not force core state.
Reproduce with the same captured export:

```sh
scripts/with-lock.sh vex-equiv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/formal/x-candidates/replay.py \
  --rtl /path/to/rv32im/VexTop.v --out /path/to/new-replay
```

The PMP export is blocked by the two undriven signals recorded in that document.
VexiiRiscv initialization was NOT RUN. No example core earned an initialization
pass. See `initialization-results.json` for both native receipts.
