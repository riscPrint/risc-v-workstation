# rvw doctor

Check the workstation and the selected core project:

```sh
rvw doctor --features sim,riscv-gcc,cosim --json
rvw doctor --features all --smoke-elf rvw/out/programs/smoke --json
rvw doctor --install sim,riscv-gcc --dry-run --json
rvw doctor --install sim,riscv-gcc
```

Default features are `sim,riscv-gcc`. `all` adds cosim, formal and gem5.
Sail is checked by the installer when `RVW_SAIL` is set.
Native checks call `scripts/install.sh --check`. The installer owns minimum
versions and warnings against `docs/TOOL_VERSIONS.md`. Doctor preserves its
output and parses version records. Version probes do not qualify a tool flow.
Unrequested backends remain visible as `skipped`. Other optional GUI tools
and IDE packages are outside this first increment.

`--install FEATURES` is the only installation path. It calls the same script.
The script asks before system packages. `--yes` approves those commands.
`--dry-run` needs `--install` and prints the installer plan without installation.
The diagnostic checks still run. Installation does not reload the parent shell.
Source `env.sh` and repeat doctor after installation.

The project check validates the project and regression tables. An optional
`project.rvw_version` is an exact pin to `rvw --version`. The shared project
loader enforces it for all project commands. Older files without a pin work.
Doctor checks C1 `info`, selected test files (ELF magic only), input declarations
and clean core/workstation commits. It does not claim a gate verdict.

`--smoke-elf` explicitly permits a native build and one run. It uses the default
config, seed 1 and 10000 cycles. It validates the written C1 result and requires
a pass without inconclusive evidence. Temporary run files are removed; the
result stays in doctor JSON. Adapter build caches can change. The adapter owns
native build locks. Without this flag build/run conformance stays inconclusive.
A smoke check does not test all options, RVFI mapping or replay completeness.

## Output and exits

`rvw.doctor/1` has `status`, `exit_code`, `checks`, `native`, `native_output`
and `backends`. Each check has a name, status, detail and fix. Native records
retain the evidence and version text. They report installation, version support,
and a match against the checked-in tested version table. A table match is not
a tested flow. Warnings outside the tested table do not
mean unsupported. Installer version refusals are errors. No complete native
combination is qualified by doctor. Skipped backends are outside the request.

Exit 0 means all requested checks are ready. Exit 1 means setup is not ready,
including a skipped build/run conformance check. Exit 2 means invalid options.
Malformed selected projects appear as failed checks with exit 1.
`rvw_doctor` exposes the same diagnostic JSON through MCP. It accepts `project`
and `features`. It cannot install tools or start a smoke build.

## Decisions and limits

Use the existing installer policy. Keep installation explicit. Never infer
adapter conformance from file presence or `info`. Input declarations are claims
that need review; doctor does not prove their completeness. Gate readiness is a
preflight check. Full C1 option conformance and C2 mapping checks remain open.
