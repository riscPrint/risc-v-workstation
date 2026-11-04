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

The graph has no physical delay model. Primary input clock intent, memory data
paths, pulse loss, metastability perturbation and protocol properties remain
unproved. Bounded FIFO topology and reconvergence checks are described below.
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

Actual reset ordering, synchronous release, isolation and functional reset
reconvergence remain unproved. Declared order and bounded merge checks are below. Matching reset signatures only remove a structural RDC candidate.
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

## Bounded topology and declared intent

The structural report now includes `depth.structures` and `depth.reset_ordering`.
A `two_ff` candidate has equal widths, two destination registers, direct edges,
and no first-stage fanout. One-bit candidates keep `cdc.sync_candidate`.
Bus chains remain `cdc.multi_bit`; two registers do not make a bus safe.

Use optional settings `intent` to name bidirectional protocols and reset order:

```json
{
  "protocols": [
    {"kind": "handshake", "forward": ["request", "req1", "req2"],
     "reverse": ["ack", "ack1", "ack2"]},
    {"kind": "async_fifo", "forward": ["writeGray", "wg1", "wg2"],
     "reverse": ["readGray", "rg1", "rg2"], "memory": "storage", "encoding": "gray"}
  ],
  "reset_order": [["sourceReset:Bool", "destinationReset:Bool"]]
}
```

Each path triple names `[source, first destination stage, second stage]`.
The handshake check requires one-bit chains in opposite clock directions.
The FIFO check requires opposite chains, equal pointer widths, a power-of-two
memory depth, one wrap bit, and synchronous read/write ports in opposite domains.
The memory path identifies the SpinalDB memory signal. The check also requires
each registered pointer to have one unconditional typed assignment of
`binary ^ (binary >> 1)` through `CastUIntToBits`. Other encodings stay invalid
for this bounded recognizer. The report retains the exact typed expression keys.
Pointer-to-address logic, pointer step behavior, full/empty logic and data
stability remain unproved. A Gray encoder match is not a one-bit-transition proof. A matching declaration gives `cdc.handshake_candidate` or
`cdc.async_fifo_candidate`. A broken topology gives the corresponding `_invalid`
finding. Both retain warnings. They do not suppress individual crossings.

`cdc.reconvergence` checks merging second-stage outputs up to the next register,
through combinational nodes. `rdc.reconvergence` checks merging register paths
with different reset signatures. These checks do not cover arbitrary sequential
latency or memory/blackbox paths. Functional reconvergence remains unrun.

Reset pairs declare source release before destination release. The check accepts
transitive order and rejects unknown reset keys and cycles. An uncovered RDC path
gets `rdc.release_order_unproved`. A covered path records
`declared_source_before_destination`; it does not prove the declared order occurs.
Asynchronous release findings remain active even with an order declaration.
Recovery/removal, metastability, release synchronization and analog timing remain
unproved. All structural reports stay inconclusive or findings.

`rvw/tests/test_lint_depth.py` contains small exact-schema reference graphs for
each matching and broken topology, merge/no-merge cases, and declared/missing
release order. These tests exercise the analyzer with controlled graphs. They do
not establish that RTL protocol behavior or extraction matches those graphs.

The extracted fixtures also include `handshake`, `handshake-broken`, `fifo`,
`fifo-broken`, `separate` and `reconverge`. The paired cases exercise topology;
they are not full handshake or FIFO implementations. The FIFO topology uses a
4-word dual-clock memory and registered Gray encoders. The broken cases add a
second input at the reverse first stage. Extracted tests also use the independent
reset design with and without a source-before-destination declaration.

Set `intent.reconvergence_depth` to 1..64 to inspect sequential reconvergence.
The default is 1. Each finding lists synchronized endpoints and minimum register
depths. A larger bound can find merges after independent pipeline registers.
This does not establish functional correlation or safe relative latency.
