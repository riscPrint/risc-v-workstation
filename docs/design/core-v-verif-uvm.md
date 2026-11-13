# CORE-V-VERIF study

Inspected on 2026-11-13 at revision
`fc3a7a3ea9d793ffe5cf0772f87d939b4bcde50c` in
[CORE-V-VERIF](https://github.com/openhwfoundation/core-v-verif/tree/fc3a7a3ea9d793ffe5cf0772f87d939b4bcde50c).
This is a source review. No upstream simulation was run.

The repository separates common components in `lib/` from core environments
in `cv32e40p/`, `cv32e40s/` and `cv32e40x/`. `lib/uvm_agents` contains OBI
memory, AXI, interrupt, debug, RVFI, RVVI and ISA coverage agents.
`cv32e40p/env/uvme/uvme_cv32e40p_env.sv` creates instruction and data memory
agents, interrupt and debug agents, a predictor and a virtual sequencer.
Its connect phase has separate predictor, scoreboard and coverage connections.
Its run phase starts instruction and data memory slave sequences.
These are useful boundaries for a reusable CPU environment.

The `lib/uvm_agents/uvma_rvvi` and `uvma_rvvi_ovpsim` directories separate
retirement reference comparison from memory stimulus. Our existing Spike DPI
replay has a similar reference boundary, but it replays a completed C1/C2
capture. It does not provide the upstream live reference interface.

Tests live under `cv32e40p/tests` with separate program, configuration and UVM
parts. Coverage code lives under `cv32e40p/env/uvme/cov`. The `tools/vptool`
directory provides verification-plan tooling. We adopt explicit named tests
and recorded seeds. We do not treat a test count as completed plan coverage.

The inspected `mk/uvmt` directory has dsim, riviera, unsim, vcs, vsim and xrun
makefiles. It has no Verilator UVM makefile. Thus this review does not establish
that its full UVM bench runs on Verilator. Our smaller pinned Accellera tests
must establish their own engine support. Successful compilation cannot establish
support for upstream constrained-random or coverage behaviour.

The root `LICENSE.md` contains Solderpad Hardware Licence 2.0. It permits an
Apache-2.0 option. Individual source and vendor notices still need inspection
before reuse. This change copies no source. It adopts structure only.

Accepted proposals are tracked in existing #296 and #178: common environment,
project bench adapters, independent reference comparison and C3 seed matrices.
Further #296 work must add a live CPU interface, retirement-to-Spike comparison,
interrupt/debug execution and native fault tests. #155 tracks declared extension
obligations. #177 tracks environment configuration control tests. This study
creates no duplicate tracking issues.
