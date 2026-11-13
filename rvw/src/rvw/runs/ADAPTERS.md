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
launch selection, core-side compatibility policy and real known-good/known-bad
history qualification remain open. No guilty commit is established by fixture
selection tests. Projects must provide adapters in each tested revision's
captured source tree; this first form cannot discover an absent old manifest.
