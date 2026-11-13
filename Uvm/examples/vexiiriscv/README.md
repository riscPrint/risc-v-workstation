# VexiiRiscv ISA captures through pyuvm

VexiiRiscv has no RVFI output. Its native project adapter captures C2 from
the upstream probe. This example checks those complete captures through the
shared pyuvm CPU environment. It is offline replay. It does not supply a
live cocotb pin binding or memory responder for VexiiRiscv.

Run the project adapter's `run-many` command on all built RV32UI and RV32UM
machine-mode ELFs. Use a private core copy and `RVW_VEX_LOCK=vex-uvm`.
Use one compiler/simulator job and a fresh run directory per program.
Keep the same jobs as a JSON array for this checker. Every job needs absolute
`elf` and `out` paths. Include `rv32ui-p-ma_data` to record the configuration's
misaligned-access gap. Do not omit a failing native program from the report.

```sh
RVW_CPU_SHIM=/path/to/matched/librvw_spike.so \
 nice -n 10 rvw/.venv/bin/python Uvm/examples/vexiiriscv/replay_suite.py \
 --jobs /path/to/jobs.json --shim /path/to/matched/librvw_spike.so \
 --out /tmp/vexii-isa-pyuvm
```

Each program gets a fresh reference, pyuvm environment and capture directory.
The checker requires C1 pass, the same ELF hash, a complete passing C2 trace,
an exact retirement count and one checked full-word tohost store.
Every retirement after that store must also match. The native probe can
retire a following instruction before the simulator observes completion. Trap cause and
tval must match an independently stepped Spike trap before handler execution.
The C2 first-handler marker must match that checked event. The normalized
scalar scoreboard receives the subsequent handler retirement with the trap
already consumed. An unsolicited handler marker fails.

The summary includes every selected program and every native failure.
It retains source hashes in C3 and reports `mode=offline-native-c2-pyuvm`.
A partial capture or a matching prefix cannot produce a checked summary.
This path does not qualify IRQ stimulus, debug, an untrapped misaligned
access or a live pyuvm VexiiRiscv binding.

## Native result on 2026-11-13

The private native VexiiRiscv adapter ran all 50 built programs on Verilator
5.049. Results: 49 passed and `rv32ui-p-ma_data` failed with C1 fail_code 668.
The pyuvm capture replay checked all 49 complete passing captures: 17,637
retirements and 245 independently matched trap events. It refused the failed
native program. Results: 49 checked, 1 failed, 0 skipped.
See [the per-program results](isa-results-2026-11-13.json).

The trace contains an initial zero-level IRQ observation. The checker requires
that level to be zero. Active IRQ stimulus remains unsupported in this profile.
The complete trace can include a retirement after the tohost store. Every
retirement in that suffix must also pass the independent scoreboard.

Local native evidence is under `$VEXRISCV/uvm-runs/vexii-full-isa/`.
The checked replay is under `$VEXRISCV/uvm-runs/vexii-isa-pyuvm-final/`.
This is not a live pyuvm VexiiRiscv binding or a full suite pass.
