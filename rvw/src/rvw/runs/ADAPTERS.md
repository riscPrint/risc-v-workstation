# Historical simulation adapters

Captured debug launches used by bisect can select a project adapter from
`.rvw-adapters.json` in the captured core source tree. Legacy projects without
that file keep their current command. The schema is `rvw.adapter-versions/1`.

```json
{
  "schema": "rvw.adapter-versions/1",
  "marker": "sim-api-version",
  "revisions": {"FULL_REVISION": "v2"},
  "adapters": {
    "v1": {"api": 1, "command": ["sim/v1/run.sh"]},
    "v2": {"api": 1, "command": ["sim/v2/run.sh"]}
  }
}
```

Exact full-revision entries take precedence. Otherwise read the marker from
the captured revision. Its stripped contents name an adapter entry. A missing
selection, unsupported API or missing executable yields no simulation result.
Bisect therefore skips that revision. It must not report the build failure as
the original core failure. The marker and executable must remain within the
captured core tree. The command is an argv array. Extra entries are literal
arguments. Use a script with a shebang for an interpreter. The launch pins that
interpreter through the existing C8 capture path.

API 1 uses the existing C1 adapter command and options. The source identity
records `adapter_selection` with schema `rvw.adapter-selection/1`, API number,
version name, tested revision, manifest digest and executable digest. The
captured source tree also binds adapter dependencies. The selected project
adapter must publish that supplied source identity in C1.

This integration applies to `DebugInputs.launcher_command`, including bisect
trials. It does not add historical adapters to BOOM or VexRiscv. Regression gate
launch selection, core-side compatibility policy and BOOM history qualification
remain open. Source-tree registries require adapters in each tested revision.
Use the project registry below for revisions that predate such a manifest.

## Project registries for older revisions

A captured debug configuration can now set a registry outside the historical
core tree:

```toml
[core]
source_env = "MY_CORE_SOURCE"
adapter_versions = "history/adapters.json"
```

The path is relative to the debug configuration. The capture freezes the
registry's directory, including its scripts and support files. Commands in
this registry resolve against that captured directory. A `marker` still
resolves against the captured core source. Exact full-revision selection keeps
its existing precedence. An unknown revision is unsupported. It does not
fall back to the current adapter. Without this setting, the original source
`.rvw-adapters.json` behavior remains unchanged.

The source identity adds `adapter_selection.manifest_scope`, with value
`project` or `source`. The launcher descriptor includes the captured registry
files as well as the captured core files. The selected adapter must preserve
`RVW_CAPTURE_SOURCE` in its C1 source record. A later core configuration does
not inherit a prior project's registry.

The [VexRiscv history recipe](../../../../examples/vexriscv/rvw/history/README.md)
uses this path on real historical example revisions with different interrupt
port inventories. The adjacent revisions identify the known M/S/U-to-M-only
change. It is a native compatibility fixture, not a newly discovered core
regression. General gate selection and a core-side interface-stability policy
remain open. These captured C1 runs do not earn C4 acceptance.
