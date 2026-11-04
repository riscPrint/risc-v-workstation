# Lint and structural CDC/RDC

## Survey and decision

The first deliverable is native lint diagnostics plus conservative register-boundary
CDC analysis from SpinalDB. It does not establish CDC signoff.

| Tool | Useful scope | Limit for this flow |
|---|---|---|
| [Verilator lint](https://verilator.org/guide/latest/warnings.html) | Elaborated RTL warnings, including UNOPTFLAT, MULTIDRIVEN and PINMISSING | No metastability or transfer protocol proof |
| [Verible](https://chipsalliance.github.io/verible/verilog_lint.html) | SystemVerilog syntax and style rules | No elaborated clock relationships |
| [Yosys check](https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/check.html) | Combinational loops, conflicting drivers and undriven wires after synthesis | Not a CDC protocol checker; adapter not implemented here |
| [VC SpyGlass CDC](https://www.synopsys.com/verification/static-and-formal-verification/vc-spyglass/vc-spyglass-cdc.html) | Structural and functional CDC, protocol assumptions, formal analysis | Commercial reference target |
| [Questa RDC](https://www.siemens.com/en-us/products/ic/questa-one/design-solutions/reset-domain-crossing/) | Functional reset crossing paths with formal analysis | Commercial reference target |

Use Verilator and Verible as native backends. Keep diagnostics, tool output,
configuration identity and waivers. Use SpinalDB edges for structural paths.
Non-Spinal designs need an importer with the same domain and graph data before
this analyzer can inspect them. RTL lint alone remains available.

## Run

Add `[lint] settings = "lint.json"` to `rvw.toml`, or use an explicit file:

```sh
rvw lint --settings lint.json --json
```

```json
{
  "schema": "rvw.lint-settings/1",
  "config": "reference",
  "top": "Reference",
  "files": ["Reference.v"],
  "db": "design.db",
  "backends": ["verilator", "verible", "structural"],
  "timeout_s": 120,
  "waivers": [
    {"config": "reference", "rule": "cdc.unsynchronized", "endpoint": "sample",
     "finding_id": "<copy the 64-character id from the reported finding>",
     "reason": "Test-only fault injection endpoint."}
  ]
}
```

Paths resolve from the settings file. Native diagnostic endpoints use the exact
`file:line:column` from the result. Structural endpoints use the destination
SpinalDB path. Each finding has an `id` derived from its diagnostic data, backend, top and
configuration. Structural findings also bind the source and destination clock/reset
domain records and signal widths. A domain change invalidates an old waiver.
Copy this value into the waiver as `finding_id`. A source or
message change gives a different ID, even at the same endpoint. Waivers need
the exact ID, rule, endpoint and configuration. Old waivers without an ID are
input errors. They do
not remove findings. Unused waivers retain `matches: 0`. A configuration mismatch
is an error. Backend suppression flags are not accepted. Native inline
suppressions already in RTL remain a limit; inspect source before signoff.

The JSON keeps raw native output, tool versions, commands, input hashes, domain
records, extractor warnings, source locations and the SpinalDB input capture.
Rule IDs use `verilator.<native-code>`, `verible.<native-rule>` and `cdc.*`.
Verible rules have warning severity. Verilator preserves warning/error severity.
Unparsed native text stays in `raw_output`. An execution failure or timeout is
inconclusive. An unparsed Verible source diagnostic also makes the backend
inconclusive, even when it also reports style warnings. A waiver cannot remove
that incomplete-check status. Missing tools and unselected backends stay visible as `not_run`.

Exit 1 means active findings. Exit 3 means incomplete evidence with no active
findings. Exit 2 means invalid input. Exit 0 requires completed selected native
checks and no missing backend. The structural backend always makes the overall
result inconclusive or findings. It never earns signoff.

## Structural scope and decisions

Read current SpinalDB data through the captured query reader. Walk data, selector
and condition dependencies through combinational nodes. Stop at each register.
Do not cross initial-value edges. Equal clock keys and edges mean the same
structural clock. Other clocks have an unknown relationship. They are checked
as possible asynchronous crossings. No frequency relationship is inferred.

A direct one-bit two-register destination chain is a `cdc.sync_candidate`.
Fanout or intervening logic prevents this match. It remains a warning. A match
does not prove pulse capture, stable data, physical placement or metastability
resolution. Multi-bit paths get `cdc.multi_bit`; other paths get
`cdc.unsynchronized`. Gray and handshake protocols need properties before a
path can be considered safe. Unknown clock identity gets `cdc.unknown_domain`.

The graph has no physical delay model. Memory paths, primary input clock intent,
async FIFO recognition, reconvergence, pulse loss, metastability perturbation
and protocol properties are not checked. Their missing evidence stays explicit.
A single-clock design can report `no_crossings_found` for register paths. This
is not a multi-clock validation result. Non-Spinal RTL needs a domain-aware
importer. Yosys is surveyed but is not a backend in this increment.

## Reset-domain crossings

The analyzer also compares reset keys, reset kind, polarity and soft-reset
controls at each register boundary. `rdc.independent_reset` marks different
reset signatures, including paths within one clock. Reset trees record each
reset control's upstream combinational cone and stop at registers. Unknown
control paths remain `unknown_control`. Missing typed control identity gets
`rdc.unknown_control`. `rdc.async_release_unproved` marks each used asynchronous
reset domain. It does not assert that a release synchronizer is absent.

Reset ordering, synchronous release, isolation and reset reconvergence remain
unproved. Matching reset signatures only remove a structural RDC candidate.
A reset-tree match does not establish safe deassertion, recovery/removal timing
or analog behavior. No declared sequencing or clock relationship is trusted as
a proof in this increment.

## Reference checks

`rvw/tests/test_lint.py` uses small exact-schema graph fixtures for unsafe
single-bit, multi-bit, two-stage, same-clock and independent-reset paths.
These tests include both candidate findings and no-crossing cases.
`SpinalDB/spinaldb/src/test/scala/spinaldb/LintFixtures.scala` emits the clock
crossing reference designs through the real extractor:

```sh
cd SpinalDB/spinaldb
../../scripts/with-lock.sh sbt nice -n 10 sbt 'Test/runMain spinaldb.LintFixtures /tmp/lint-fixtures'
```

Use each generated `design.db` in a structural-only settings file. The `single`
design must have no clock crossings. `unsafe` must report an unsynchronized
crossing. `sync` must report a candidate, and `bus` must report a multi-bit
crossing. None earns protocol safety. MCP exposes the same report through
`lint_report` with an explicit settings path.

The same entry emits `reset-shared`, `reset-independent` and `reset-async`.
The shared synchronous reset has no RDC candidate. Independent reset controls
must report `rdc.independent_reset`. Asynchronous controls must also report
`rdc.async_release_unproved`.

Run the extracted-design assertions from the workstation root:

```sh
RVW_LINT_FIXTURES=/tmp/lint-fixtures rvw/.venv/bin/python -m pytest rvw/tests/test_lint_extracted.py -q
```

Install the pinned Verible backend with `scripts/install.sh --with-lint`.
Source `env.sh` before `rvw lint`. The installer verifies SHA256 and checks the
native executable. Use `--with-lint --check` for a read-only version check.
