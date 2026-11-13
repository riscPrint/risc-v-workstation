# Full built RV32IM ISA campaign

Use the same private VexRiscv source copy and matched VexTop RTL as the live
binding. Run all built RV32UI and RV32UM machine-mode programs in one native
cocotb build. Each program resets the RTL and creates a fresh pyuvm CPU
environment, memory model, independent Spike instance and capture directory.

```sh
scripts/with-lock.sh vex-uvm nice -n 10 rvw/.venv/bin/python \
 Uvm/examples/vexriscv/isa_suite.py \
 --programs "$VEXRISCV/rvw/out/isa" --rtl Uvm/examples/vexriscv/VexTop.v \
 --shim Cosim/build/librvw_spike.so --out /tmp/vex-full-isa
```

Discovery includes every ELF whose name starts with `rv32ui-p-` or
`rv32um-p-`. It includes `rv32ui-p-ma_data`. It ignores disassembly files.
The report lists all selected programs and missing comparison summaries.
It does not omit failures to claim a full pass. A checked summary requires
the final tohost store and all preceding retirement and trap comparisons.
The output keeps per-program checks, cycles and observed coverage.

This scope is the built RV32IM machine-mode riscv-tests set. It is not all
riscv-tests targets, privilege profiles or extensions. Source identity in
standalone C3 remains incomplete. This campaign does not earn C4 acceptance.

## Native result on 2026-11-13

Verilator 5.052 and cocotb 2.1.0 ran all 50 built programs through live
pyuvm. Results: 49 passed, 1 failed, 0 skipped. `rv32ui-p-ma_data` failed
with tohost 1337. It remains in the report. The 49 complete passing programs
checked 17,735 retirements and 196 traps against independent Spike.
See [the per-program results](isa-results-2026-11-13.json).

Local C3, logs and per-program summaries are under
`$VEXRISCV/uvm-runs/full-isa-pyuvm/`. These results do not establish a full
suite pass or misaligned-access support for the selected trap profile.
