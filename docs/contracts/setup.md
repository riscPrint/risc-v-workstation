# Setup and adapter selection contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Captured historical adapter selection

An optional captured `.rvw-adapters.json` uses `rvw.adapter-versions/1`.
Exact revision mappings take precedence over a captured version marker.
Only adapter API 1 is supported. Its command uses C1 options. Paths stay inside
the captured core tree. Selection pins the interpreter under C8 and adds
`adapter_selection` to source identity. It records API, version, revision,
manifest SHA-256 and executable SHA-256. Unsupported revisions produce no run
and remain skipped bisect evidence. See `rvw/src/rvw/runs/ADAPTERS.md` for the
manifest and the current debug-launch-only integration boundary.

## Limit ownership

Backend semantics: [#116](https://github.com/riscPrint/risc-v-workstation/issues/116). Multi-hart: [#90](https://github.com/riscPrint/risc-v-workstation/issues/90). Faulting memory effects: [#93](https://github.com/riscPrint/risc-v-workstation/issues/93). Database consumers: [#69](https://github.com/riscPrint/risc-v-workstation/issues/69).

Retained limit: All documented unsupported capture structures, size bounds and synchronous-state restrictions remain in force. C1 cannot report success without captured model evidence. C9 does not claim complete C8 capture, immutable generations or a gate verdict. No dedicated issue owns broader C9 capture.

## Setup diagnostics and project version pin

`[project].rvw_version` is an optional exact pin to `rvw --version`. The project
loader rejects a mismatch. Existing projects without this key remain valid.
`rvw doctor --json` and MCP `rvw_doctor` return `rvw.doctor/1`. See the
[doctor contract](../rvw/src/rvw/doctor/README.md#output-and-exits) for fields
and exits. Diagnostic readiness does not imply a gate accept or native flow qualification.
