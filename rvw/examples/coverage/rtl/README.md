# Small RTL sampling example

Run `demo.py OUT` with the workstation Python environment under a shared
build lock. OUT must be new. Use Verilator 5.052 or later.
See `rvw/src/rvw/cov/README.md` for the plan, sample and sequence contracts.
The demo uses SystemVerilog source, so it supplies null Scala links.
The VexRiscv example uses real Spinal HGLDD links.
