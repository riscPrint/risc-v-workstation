# Core setup playbook (mapped adapter)

`rvw init` wrote a working C1 adapter: the generic RiscvSim `MappedAdapter` reads
`rvw/core-map.json`. Review every entry against the core before trusting a result.

1. Check `isa`, `reset_pc` and `ram` against the core specification.
2. Check each bus mapping and protocol. See RiscvSim/README.md, "Mapped adapter".
3. Check `constants`: unmapped inputs are tied to the listed values.
4. Build the smoke ELF: `rvw/build-smoke.sh`. Then run
   `rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/smoke --rvfi-trace --json`.
5. Without RVFI ports, completion comes from bus stores to `tohost` and C2 is unavailable.
   Add RVFI with `rvw/templates/RvfiPort.scala` (Spinal) or the core's riscv-formal ports.
6. Review `rvw/cosim.json` (privilege modes, misaligned policy, PMP, ECALL `tval`).
   It uses the platform defaults; check them.
7. Run `rvw doctor --json` and `rvw doctor --conformance --json`.
8. Review all result-changing inputs before enabling `input_complete` and `identity`.
9. Commit the project files before a gate.
