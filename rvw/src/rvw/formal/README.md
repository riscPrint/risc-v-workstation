# `rvw formal`

Bounded RTL hygiene checks backed by Yosys and SymbiYosys (`bmc`, `from-sim`, `xprop`, `x-context`, `x-sweep`). See [SpinalChecks](../../../../SpinalChecks/README.md) for elaborated assertion generation.

## Scope

- **Kept here**: bounded checks from reset (`bmc`), simulation-state checkpoints (`from-sim`), and X-propagation / unreset-state triage (`xprop`, `x-context`, `x-sweep`), plus the shared helpers used by `checks`, `soc`, `sec`, and `lint`.
- **Single-clock default**: flows require one rising-edge clock and synchronous state controls unless `--event-model` is supplied; missing replay memories start unconstrained and bounded passes do not establish unbounded proofs.
- **Unbounded proofs (new centerpiece)**: agent-native compositional hardware verification in **Lean 4** lowers Spinal/Yosys RTL into hierarchical `BitVec` transition systems anchored on Sail RISC-V. See [docs/LEAN_VERIFICATION_SPIKE.md](../../../../docs/LEAN_VERIFICATION_SPIKE.md).

## Commands

- `rvw formal bmc --verilog ... --top ... --out ... [--depth 20] [--checks <top>.checks.json]`
- `rvw formal from-sim --verilog ... --top ... --trace ... --cycle N --out ...`
- `rvw formal xprop --verilog ... --top ... --out ... [--outputs] [--checks ...] [--replay icarus]`
- `rvw formal x-context --verilog ... --top ... --signal ... --tie ... --timeout S --out ...`
- `rvw formal x-sweep --verilog ... --top ... --out ...`
