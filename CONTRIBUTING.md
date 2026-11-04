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
uv pip install -e '.[dev,mcp]'
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
Update [PLATFORM_CONTRACTS.md](docs/PLATFORM_CONTRACTS.md) in the same commit
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
