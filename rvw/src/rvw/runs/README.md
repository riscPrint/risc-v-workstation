# Run infrastructure and portable replay

This package reads C1 results, captures run inputs and invokes project adapters.
See [adapter versions](ADAPTERS.md) for historical source selection.

## Single-file replay

`rvw replay-pack RUN --recipe PROJECT/rvw/replay.json --out failure.rvw`
creates one offline ZIP archive. It contains the ELF, seeded run options,
interrupt schedule, captured simulation map, complete expected C2 events,
a from-reset trace checkpoint, and Git bundles for the recorded core and
adapter revisions. Tracked patches and declared untracked source inputs are
included. Source snapshots are rebuilt at replay time. No network fetch is
needed for those source revisions.

```sh
rvw replay-pack failed-run --recipe /path/to/project/rvw/replay.json --out failure.rvw
rvw replay failure.rvw --out new-reproduction --lock project-private-lock
```

The output directory must be new. Every archived input hash is checked before
source checkout or adapter execution. The runner reconstructs the source trees
and uses the current installed Python with the archived rvw package. It then
requires the recorded ELF, seed, cycle limit, memory timing, terminal status,
failure signature, RTL hash and complete architectural C2 events to match.
Semantic C2 header fields must match. Only the relocated ELF path and source
provenance are excluded from header comparison. Checkpoint prefix and suffix hashes must also match.
A mismatch is reported as `mismatch`, never as reproduction.

The recipe is project data under `rvw.replay-adapter/1`. It supplies `command`,
`source_env`, optional `lock_env` and `host_environment`, and `source_inputs` roots for `tools` and
`core`. Command tokens support `{python}`, `{tools}` and `{core}`. The example
recipe stays beside the VexRiscv project. Generic code has no core signal names.
MCP tools are `replay_pack` and `replay_run`.

## Decisions and limits

The archive carries source history at the pinned revisions. This costs more
bytes than an ELF-only recipe but permits offline source reconstruction.
Declared host-tool values such as `JAVA_HOME` and `PATH` come from the target
environment. Unknown absolute environment paths refuse packaging. The runner
creates a small Python environment with the archived package on its source path.
The target machine still needs the project's build tools, JVM, native compiler,
Verilator and cached dependency packages. Tool binaries are not archived.
A successful replay reports reproduced behavior. It does not earn C4 acceptance.

The checkpoint is a deterministic trace bookmark. Replay starts from reset
and checks both sides of that boundary. It does not restore live RTL state.
Live bridge checkpoints have a separate same-build contract. Boot-payload,
hart-image, fault-file, stimulus-file, interactive debug and trace-ingress inputs currently
refuse packaging. Recipes must
name all untracked source inputs that affect the adapter. Original Git dirty
flags remain in the manifest. Patched sources are identified by their patch
hashes as well as the baseline revision.

Fixture tests remove the original source directories and replay from the
archive. Native examples provide a separate RTL check. Cross-machine native
execution must be reported separately from a local relocation check.

## Native sample

The VexRiscv sample on 2026-11-13 packed one 33.6 MB archive. A new source
location rebuilt the captured snapshots and reproduced a failure at cycle
9,023 with 2,005 retirements and fail code 3. All sixteen checks passed,
including semantic C2 header, complete C2 events, RTL hash and the checkpoint
prefix/suffix at cycle 4,500. This is a local relocation result. Execution on
a second machine was NOT RUN. See
[the sample](../../../../examples/vexriscv/rvw/replay-results.json).
