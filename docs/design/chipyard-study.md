# Chipyard study

Reviewed on 2026-11-13. This note covers simulation and integration. It does
not propose an FPGA, ASIC or PPA flow.

## Configuration

Chipyard composes named config fragments. Later choices can replace parameter
values. Its documentation also notes that parameter discovery is difficult.
For SpinalSoc, adopt ordered JSON fragments with an emitted effective config.
Keep core and peripheral bindings explicit. Do not import Rocket's parameter
system into this small library. See the [config documentation](https://chipyard.readthedocs.io/en/latest/chipyard-basics/configs-parameters-mixins/).

## Harness binders and bridges

Chipyard separates chip IO creation from test-harness device bindings. A
harness can select software memory models or FireSim bridges for the same
chip IO. Keep this separation in SpinalSoc: project wrappers select RTL;
exports name physical ports; simulation owns UART decoding and external IRQ
schedules. Do not put simulated devices inside the core wrapper. FireSim
integration needs an independent bridge/timing contract and is deferred.
See [IOBinders and HarnessBinders](https://chipyard.readthedocs.io/en/latest/customization/iobinders/).

## Simulation and candidate contributions

Chipyard documents Verilator/VCS runs, custom programs, memory loading and
waveforms. A small contribution could show a C1 adapter around its Verilator
launcher. That would let Chipyard users use rvw regress and failure bundles.
A second contribution could map its retirement output into C2 for rvw cosim.
Each adapter must record config, source, ELF and generated RTL identity.
A third candidate is an MCP usage guide for these generic commands. None of
these requires a Spinal design database. See [software RTL simulation](https://chipyard.readthedocs.io/en/latest/simulation/software-rtl-simulation/).

## Adoption and follow-up

The composer already separates explicit RTL binders from the example harness.
This change adds ordered config fragments and records their hashes and the
effective configuration. Native SoC results remain separate from generation.
Follow-up: [Chipyard C1 adapter](https://github.com/riscPrint/risc-v-workstation/issues/722)
and [retirement/C2 adapter](https://github.com/riscPrint/risc-v-workstation/issues/723).
No upstream issue or PR was sent. Upstream contributions need owner approval.
