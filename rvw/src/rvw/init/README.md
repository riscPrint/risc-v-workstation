# rvw init

Minimal supported path: an existing Spinal/sbt core repository with `build.sbt`
and Scala sources under `src`. Start with one config and one smoke ELF.
The command creates setup stubs. It cannot infer a safe bus or RVFI mapping.

```sh
cd /path/to/core
rvw init --isa rv32im --dry-run --json
rvw init --isa rv32im
rvw doctor --json
```

The command scans the build for literal Spinal version declarations and the
sources for candidate `Component` classes. These are hints, not elaboration.
If exactly one literal ISA string is found, it can use that string. Otherwise
supply `--isa`. There is no interactive prompt. `--xlen` can check the width.
`--name` overrides the directory name. A mismatched width is an error.
Verify ISA extensions against the core specification.

Files:

- `rvw.toml`: exact `rvw --version` pin, one `default` config and a smoke suite.
- `rvw/run.sh`: executable C1 info stub. Build and run return 2.
- `rvw/src/main/scala/rvwcore/CoreAdapter.scala`: typed RiscvSim adapter skeleton.
- `rvw/.gitignore`: ignores `out/` and local sbt output.
- `rvw/README.md`: the core's setup playbook and remaining actions.

`--dry-run` returns every planned file with its full text. It writes nothing.
The command checks all target conflicts before writing. It refuses any existing
target unless `--force` is set. `--force` replaces only the listed files. It
still refuses directory targets and blocked parent paths. Keep edited adapters
before using `--force`. Existing root `.gitignore` and `AGENTS.md` stay intact.

`--json` returns `rvw.init/1` with `status`, `exit_code`, `root`, `files`,
`overwritten`, `isa`, `xlen`, `spinal_versions`, `candidate_tops` and `next`.
Exit 0 means created or planned. Exit 2 means invalid input or write failure.
Failures include an `error` string. No MCP mutation tool is added.

## Decisions and limits

The output passes the shared project and regression loaders. Doctor reports
`project: ready` and `adapter.info: ready`. It returns exit 1 until the adapter,
tests, input declarations and clean commits are ready. A stub must not earn a
ready setup verdict. Use the core's playbook to finish these actions.

This increment does not generate a build definition, cosim memory map or
SpinalDB entry. Connect the skeleton to the existing core build with the generic
RiscvSim library. Use a shipped launcher for native identity and supervision.
Preserve the actual source and native-tool inputs. Review all capture claims.
Automatic build wiring, linker-script detection, optional cosim/SpinalDB files
and broader build detection remain open under #36. This command makes no
integration-model decision under #34.
