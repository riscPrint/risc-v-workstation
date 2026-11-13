# Contributing

Use [GitHub issues](https://github.com/riscPrint/risc-v-workstation/issues) as the task tracker.
Read [AGENTS.md](AGENTS.md) and the README for the tool you change.
Check for an existing module before you add code. Keep each change small.
State the files you own, dependencies and acceptance checks in the issue.

## Setup

Install Python 3.11 or later and `uv`. From this checkout, run:

```sh
scripts/install.sh
source env.sh
scripts/install.sh --check
cd rvw
uv sync --locked --extra dev --extra mcp
cd ..
```

The installer creates the Python environment. Use `--dry-run` to inspect actions.
Add `--with-sim`, `--with-riscv-gcc`, `--with-cosim`, `--with-formal` or
`--with-gem5` when needed. Use the same flags with `--check`.
System package commands need approval unless you supply `--yes`.
See [Bring your own core](docs/BRING_YOUR_OWN_CORE.md) for native tool setup.
Keep your core in a separate repository with its own `rvw.toml` and adapters.

## Tests and locks

This fast Python check uses fixtures. It needs no private BOOM checkout or
native EDA tools. Run it from the workstation root:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_capture.py rvw/tests/test_generation.py rvw/tests/test_project.py -q
```

Run tests for the tool you change. Before you submit a PR, run the Python suite:

```sh
scripts/with-lock.sh suite nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests -q
```

Optional native tests can skip when Spike, Sail, RISC-V GCC or formal tools are
missing. Report exact pass, fail and skip counts. A skip does not prove support.
See [AGENTS.md](AGENTS.md#tests) for Scala, Rust and extension tests.

Use `scripts/with-lock.sh boom nice -n 10 COMMAND` for BOOM builds and long runs.
Use `vex` for VexRiscv, `sbt` for shared sbt outputs, `suite` for the full Python
suite and `gem5` for gem5 jobs. Run one heavy job at a time.
Do not build in another contributor's core checkout.

## Change rules

Keep shared code generic. Do not name a core's signals, configs or tests in
`rvw/src/`, `RiscvSim/src/` or the Spinal libraries. Put new core details in its
repository beside `rvw.toml`. Keep the existing bundled adapters for compatibility.
Update the format's file under `docs/contracts/` (index: [PLATFORM_CONTRACTS.md](docs/PLATFORM_CONTRACTS.md)) in the same commit
when you change a shared format.

Never report a pass, match, accept or exclusion without enough evidence.
Use `inconclusive`, `no_checks` or an error for missing or ambiguous evidence.
Give each bug fix a test that fails before the fix. Gate accept needs committed
base and candidate revisions. See C8 for the threat model.

Do not add history, validation, evidence or review-record files to the repository.
Put measured results and dependency-advisory dispositions in the PR body or issue.
For advisory triage, give the date, package version, advisory, reachability,
disposition and remaining checks. Do not treat an old audit note as current status.

## Commits and pull requests

Follow [AGENTS.md](AGENTS.md#commits-and-pull-requests).
Use Conventional Commits for commits and PR titles: `type(scope): summary`.
Use an imperative, lower case summary with no full stop and at most 72 characters.
Types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`
and `revert`. For breaking changes, add `!` after the scope, add a
`BREAKING CHANGE:` footer and update the docs.
Link the issue in a commit footer: `Refs: #N` or `Closes: #N`.

Use the PR template sections: `## Summary`, `## Testing` and `## Issues`.
State owned scope, dependencies, acceptance checks and exact test commands.
Include pass and skip counts, failures and checks not run.
Use `Closes #N` only when all acceptance items are complete.
Otherwise use `Refs #N` and list what remains. Keep task status in GitHub issues.
Report security problems through [SECURITY.md](SECURITY.md).

## Local CI

The workflows use one macOS ARM64 runner with labels `self-hosted`, `macOS`,
`ARM64`, `rvw-local`. It accepts one job at a time. Do not change the runner service
or cancel runs as part of a definition change.

Run a tier from the repository root:

```sh
scripts/ci-local.sh --tier fast
scripts/ci-local.sh --tier native-light
scripts/ci-local.sh --tier examples
scripts/ci-local.sh --tier nightly
```

Fast needs Python 3.11+, uv 0.13.6+, Git and Bash. Use `CI_PYTHON` to select Python.
It runs the Python fast set, including release hygiene. The command-reference
check is selected but remains explicitly deferred until the owner restores it.
It needs no native tools. Its Python test target is less than 300 seconds.

Native-light runs tiny fixtures with a 120-second process-group cap. Its tool
names are in `scripts/ci-tiers.json`. New package fixtures use the `native_light`
marker with exact tool names from `rvw/src/rvw/doctor/tools.json`.
Missing tools produce a skip with its reason. Presence does not prove operation.

Examples runs VexRiscv and VexiiRiscv smoke suites through `rvw regress`.
It caches pinned core repositories in `~/.cache/rvw-ci/cores`.
Use `RVW_CI_CORE_CACHE` to select another cache. Builds use private core copies.
It builds only the two smoke programs. It does not need riscv-tests.
It expects JDK, sbt, Verilator and RISC-V GCC from the inventory.

Nightly runs the slow Python set, Scala suites, Rust, VS Code, ComponentSims and
VIP tests. Scala needs JDK 21 and sbt. Rust needs Cargo. VS Code needs Node 22
and npm. ComponentSims needs a C++17 compiler. Other native tools come from the
inventory. macOS jobs expect these tools. They do not install system packages.
Use `CI_COMPONENT=python|scala|rust|javascript|components|vip` for one component.
Use `CI_SCALA_PROJECT` for one listed Scala project.
Use `CI_SHARD=0/4` through `3/4` for disjoint slow Python shards.
Nightly is scheduled for 03:23 UTC. The definitions also allow manual dispatch.
No completed run is implied by these definitions.

The script copies tracked files, including local edits, to a private directory.
Add new files to Git before use. It creates a venv and uses locked dependencies.
It uses the machine-wide `suite` and `sbt` locks and `nice -n 10`.
Reports survive cleanup in `rvw/out/ci`. Use `CI_REPORT_DIR` to change this path.
Job summaries give test counts, slow tests, skip reasons and absent tools.
A setup failure has no test counts. It must not report tests as passed.

PR jobs use changed paths. Docs-only changes run hygiene and the selected
command-reference check. Python changes run the fast set. Rust, JavaScript and
Scala checks run for their paths. CI changes select all jobs.
Superseded PR runs are cancelled by branch. Keep `Fast` as the required-check
name in repository settings. Conventional Commits remains a separate check.

Linux definitions use `ubuntu-latest`. Both remain disabled unless the single
repository variable `RVW_LINUX_CI` equals `enabled`. Linux is untested.
Their apt recipe reads the tier's tools from the inventory. Source-only tools
are not installed by apt. Missing tools remain explicit skips.
Manual installer and Linux boot workflows retain their existing separate controls.

This work is tracked in [#16](https://github.com/riscPrint/risc-v-workstation/issues/16)
and [#41](https://github.com/riscPrint/risc-v-workstation/issues/41).
