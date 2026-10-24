# Changelog

Each release lists what changed and, for breaking changes, how to update a core project.

## v0.1.0-alpha (2026-10-24)

First alpha release. The workstation runs, judges and debugs a Spinal RISC-V core through one
command line (`rvw`) and one MCP server (`rvw mcp`). BOOM and VexRiscv are the checked cores.
Supported platforms: macOS and Linux. The license is not chosen yet.

### Install

```sh
git clone https://github.com/riscPrint/risc-v-workstation.git
cd risc-v-workstation
scripts/install.sh --with-sim --with-riscv-gcc --with-cosim   # add --with-formal, --with-gem5 as needed
source env.sh
```

Then follow `docs/AGENT_SETUP.md` (agents) or `docs/BRING_YOUR_OWN_CORE.md` (people) to connect a core.

### Ready

- `rvw regress run` and `rvw regress gate` on committed revisions, without known-failure waivers.
  A gate on uncommitted work runs the tests and prints `TESTS PASS` / `NOT ACCEPTED`; commit and
  rerun to earn `ACCEPT`. Passing results are reused when the generated Verilog is unchanged.
- `rvw cosim` against Spike (lockstep, first difference) and Sail.
- `rvw formal bmc`, `from-sim` and `xprop` on single-clock designs with synchronous state.
- `rvw cov prove`, `merge`, `report`, `select` and `functional`.
- `rvw query` (drivers, loads, path, where, hardware diff) on a SpinalDB design database.
- `rvw bundle`, `reduce`, `bisect`, `wave` and `perf`.
- `rvw mcp`: all of the above as MCP tools for agents.
- Project mode: a core repository brings its own `rvw.toml`, adapter and settings
  (`--project`, `RVW_PROJECT` or upward discovery). `--core boom` keeps the shipped example.
- `scripts/install.sh` for macOS (Homebrew) and Linux (apt, dnf), with `--check` and `--dry-run`.

### Experimental (check results by hand)

- Known-failure waivers and failure signatures.
- Gates on stored result folders, and performance metrics in the gate.
- `rvw cov mutate` (mcy).
- SpinalChecks generated checks. On BOOM, 24 of 516 checks fire and are not triaged yet.
- `rvw arch` (gem5 out-of-order model, calibrated against the RTL). Out-of-order RV64 cores only;
  IPC comparison, no fitting. Tuning a core's model belongs to that core's project.

### Formats

Shared formats are in `docs/PLATFORM_CONTRACTS.md` (C1–C8). This release writes C4 verdicts as
`/2` (separate test outcome and acceptance status), mutation reports as `rvw.mutation/2` and design
databases as `rvw.designdb/20`. Older C4 `/1` verdicts, `/1` mutation results and old proof folders
without saved harness paths must be regenerated.

### Known limits

- Cosim does not compare FP registers or `fflags`; no vector, hypervisor, debug mode or multi-hart.
- Four BOOM assumptions remain in generic code (#6–#9).
- Each run re-elaborates the design (BOOM: 15–25 s).
- No CI yet (#16). Installer options other than core and `--with-sim` are not fully verified (#17).

The roadmap is in the GitHub issues: milestones "v0.2 (near term)" and "Later phases", and the
`idea` label. The integration model for core projects is open for decision in #34.
