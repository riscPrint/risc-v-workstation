# Lint and structural CDC/RDC

## Survey and decision

The first deliverable is native lint diagnostics plus conservative register-boundary
CDC analysis from SpinalDB. It does not establish CDC signoff.

| Tool | Useful scope | Limit for this flow |
|---|---|---|
| [Verilator lint](https://verilator.org/guide/latest/warnings.html) | Elaborated RTL warnings, including UNOPTFLAT, MULTIDRIVEN and PINMISSING | No metastability or transfer protocol proof |
| [Verible](https://chipsalliance.github.io/verible/verilog_lint.html) | SystemVerilog syntax and style rules | No elaborated clock relationships |
| [Yosys check](https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/check.html) | Combinational loops, conflicting drivers and undriven wires after synthesis | Native connectivity adapter; not a CDC protocol checker |
| [VC SpyGlass CDC](https://www.synopsys.com/verification/static-and-formal-verification/vc-spyglass/vc-spyglass-cdc.html) | Structural and functional CDC, protocol assumptions, formal analysis | Commercial reference target |
| [Questa RDC](https://www.siemens.com/en-us/products/ic/questa-one/design-solutions/reset-domain-crossing/) | Functional reset crossing paths with formal analysis | Commercial reference target |

Use Verilator and Verible as native backends. Keep diagnostics, tool output,
configuration identity and waivers. Use SpinalDB edges for structural paths.
Non-Spinal designs use `rvw query build-hdl`: it writes clock domains from
the Yosys flip-flop cells (see the SpinalDB README). The lint graph reads the
importer's `Yosys net alias` rows: hidden names are dropped, the bits of a
register vector merge into its one visible name, and other name-to-bit links stay
as connectivity that the loop check ignores. A name is used or driven when one
of its bits is. Constant ties count as drivers. Synchronous resets in plain mux
logic stay data. On the SERV core (`serv_top`, 219 registers, Yosys import)
the `rules`, `structural` and `sdc` backends run in under one second with no
rule findings after these fixes; Yosys `check` agrees that it has no loop.

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
structural clock. Other relationships come from clock inference and
declarations (below). No frequency relationship is inferred.

The crossing classes are below. A synchronizer match does not prove pulse
capture, stable data, physical placement or metastability resolution. Gray and
handshake protocols need properties before a path can be considered safe.
Unknown clock identity gets `cdc.unknown_domain`.

The graph has no physical delay model. Primary input clock intent, memory data
paths, pulse loss, metastability perturbation and protocol properties remain
unproved. Bounded FIFO topology and reconvergence checks are described below.
A single-clock design can report `no_crossings_found` for register paths. This
is not a multi-clock validation result. Non-Spinal RTL needs a domain-aware
importer. The optional Yosys backend checks native connectivity. It does not infer clock domains.

## RTL lint rules

Select backend `rules` to run lint rules on the design database (`db`). These
rules read the elaborated graph, so they also work on `rvw query build-hdl`
databases. Defaults:

| Rule | Severity | Check |
|---|---|---|
| `lint.comb_loop` | error | Cycle through wires (strongly connected components); `members` lists the loop. |
| `lint.multiple_drivers` | error | Data assignments to one signal from more than one component. |
| `lint.input_driven` | error | A toplevel input is assigned inside the design. |
| `lint.latch` | error | A wire is assigned only under conditions. |
| `lint.width_truncation` / `lint.width_extension` | warning / info | A typed `Resize` key changes the width. |
| `lint.unused` | info | An internal signal without loads (Spinal prunes most; pruned signals are skipped). |
| `lint.unconnected_output` | warning | A child output port without loads. |
| `lint.undriven` | error | A wire without assignments or inputs, not a toplevel input, clock-domain net or blackbox output. |
| `lint.constant_register` | info | A register that is never assigned after reset. |
| `lint.fsm_unreachable` | warning | An enum state that no assignment in the state register's same-type cone writes. The `fsm` list keeps `checked` or `inconclusive` per register. |
| `lint.no_reset` | info | A register without `init` in a clock domain with a reset. |
| `lint.clock_as_data` | error | A clock net reaches register data or control logic. |
| `lint.naming` | warning | A Verilog/SystemVerilog keyword as a name, or a mismatch with a configured pattern. |
| `lint.max_fanout` | warning | Fan-out above `limit` (default 512). |

Settings `rules` change severities (`off`, `info`, `warning`, `error`) and
parameters: `{"lint.no_reset": "off", "lint.max_fanout": {"limit": 64},
"lint.naming": {"ports": "[a-z][A-Za-z0-9_]*", "registers": "...",
"signals": "..."}}`. Unknown rules or bad patterns are input errors. Exact-ID
waivers apply as for the other backends. The `fsm_unreachable` check finds
states that are never written. It does not prove that written states are
reachable. Blackbox edges make the backend `inconclusive`.

MCP: `lint_report` (`settings`, optional `sarif`) and `lint_emit` (`settings`,
`out`, optional `sarif`) run the same report as background jobs.

`rvw lint --sarif PATH` also writes all findings (all backends and stale
waivers) as SARIF 2.1.0. Each result keeps the rule, level (`info` becomes
`note`), file and line, the endpoint as a logical location, the finding `id` as
fingerprint `rvw/finding-id`, and a suppression with the reason for each
waived finding.

## Clock inference and synchronizer classes

`cdc.py` infers each clock domain's clock from its driver in the graph:
`primary` (a toplevel input, through wires), `divided` (driven by a register;
`divide_by: 2` for a toggling one-bit register), `gated` (a clock combined with
enables), `generated` (a blackbox output, for example a PLL) or `unknown`.
`master` is the primary input behind a divided or gated clock. Two clock
records are `same` (equal key and edge), `related` (same master),
`asynchronous` (different masters), `declared_synchronous` or
`declared_asynchronous` (from `intent.clocks`, or Spinal `setSynchronousWith`,
read from `ClockSyncTag` signal tags) or `unknown`. SpinalChecks `CdcChecks`
emits Gray and pulse-width checks from the same Spinal clock-domain data inside
the design. Each
`intent.clocks` row has `clocks` (two or more clock paths), `relationship` and
`reason`. Unknown clock paths are input errors.

Each register path between different clock records gets one class in
`crossings[].kind`:

| Kind | Rule | Structure |
|---|---|---|
| `synchronous_related` | `cdc.related_clock_crossing` (info) | Related or declared synchronous clocks. Timing analysis owns the path. |
| `glitch_before_sync` | `cdc.comb_before_sync` (error) | Combinational logic with more than one input before a synchronizer (two or more stages, or a `crossClockDomain` tag). |
| `first_stage_fanout` | `cdc.sync_stage_fanout` (error) | The first stage drives more than the next stage. |
| `sync_2ff`, `sync_3ff`, ... | `cdc.sync_candidate` | One-bit chain of 2 to 6 stages through single-input wires, without fan-out. |
| `gray_sync` | `cdc.gray_candidate` (info) | Multi-bit chain whose source register is assigned `binary ^ (binary >> 1)`. Emits a `gray_code` obligation. |
| `qualified_data` | `cdc.qualified_data_candidate` (info) | Multi-bit data sampled under the output of a one-bit synchronizer (mux or enable). Emits a `data_stable` obligation. |
| `multi_bit` | `cdc.multi_bit` | Other multi-bit paths, including `BufferCC` on a non-Gray bus. |
| `unsynchronized` | `cdc.unsynchronized` | Other one-bit paths. |

Spinal library structures are recognized from `components.class_name`:
`BufferCC`, `StreamCCByToggle`, `FlowCCByToggle`, `PulseCCByToggle`,
`StreamFifoCC`, `DataCC` and `ResetCtrl`. The crossing records the library
component in `library`. A memory written and read in unrelated clocks gives
`cdc.async_fifo_candidate` (info) inside `StreamFifoCC`, else
`cdc.memory_crossing`. `cdc.fanout_before_sync` marks one source that crosses
into several registers of one clock. `cdc.hierarchy` groups findings by the
endpoint's component path. Existing exact-ID waivers apply to all these rules.

## Functional CDC step

`rvw lint --settings lint.json --emit DIR` writes the protocol assertions for
the obligations into a new or empty directory:

- `cdc_obligations.json` (`rvw.cdc-obligations/1`): each obligation with
  `kind`, `signal`, `width`, `clock_domain`, `destination` and `bind` (Verilog
  module and local port names) or `unbound_reason`.
- `cdc_checks.sv`: checker modules `rvw_cdc_gray` (at most one bit changes per
  source clock) and `rvw_cdc_stable` (data is stable while its qualifier stays
  asserted), and one `bind` line per bound obligation. Use it with Verilator
  `--assert` or another simulator with `bind`.
- `checked/`: copies of the settings `files` with the checker instances inside
  the target modules, and `rvw_cdc_checkers.sv`. Yosys does not elaborate
  `bind`; give these files to `rvw formal bmc|prove`.

- `rvw_cdc_toggle` (`toggle_stable`): when the qualifier's source register
  toggles itself (a toggle handshake such as `StreamCCByToggle`), data changes
  only in the cycle the request toggles.

The checkers use one clock (the source clock) and immediate assertions. The
`data_stable` checker uses level semantics. `test_lint_hdl.py` runs a Verilog
toggle handshake through `build-hdl`, `--emit` and a Yosys BMC: the correct
design holds for 12 steps and a design that changes data between toggles fails. Emission is never a pass; the obligations stay unproved until a formal
or simulation run checks them.

## Timing-constraint intent (SDC)

Select backend `sdc` to generate constraints from clock-domain data and to
check a project SDC file. Settings `sdc`:

```json
{"clocks": {"clkB": {"period_ns": 8}},
 "generated": {"pll.clkOut": {"source": "clkIn", "multiply_by": 4, "divide_by": 1}},
 "multicycle": [{"from": "core.a", "to": "core.b", "setup": 2, "reason": "enable every 2nd cycle"}],
 "check": "constraints.sdc",
 "register_pattern": "{path}_reg*", "output_pin": "Q"}
```

Periods come from `sdc.clocks`, else from SpinalDB `clock_frequencies` (Spinal
`FixedFrequency`). Generation (`backends.sdc.sdc`, also `constraints.sdc` with
`--emit`):

- `create_clock` for each primary clock with a period. A primary clock without a
  period, or a generated/unknown clock without an `sdc.generated` row, gets
  `sdc.unconstrained_clock` (error).
- `create_generated_clock -divide_by 2` for a toggling register clock; ratios
  from `sdc.generated` for blackbox (PLL) clocks. Gated clocks get a comment:
  STA propagates the master clock through the gate.
- One exception per recognized safe crossing (`sync_Nff`, `gray_sync`,
  `qualified_data`): `set_max_delay -datapath_only` from Spinal
  `crossClockMaxDelay` (cycles times the source or target period), else
  `set_false_path`. Spinal `crossClockFalsePath` tags (reset synchronizers)
  give `set_false_path -to`. Unsafe crossings get no exception and
  `sdc.unsafe_crossing`.
- `set_multicycle_path` setup and hold (default `setup - 1`) for each declared
  multicycle path. The path must be an elaborated register path, else
  `sdc.unmatched_multicycle` (error).
- A commented `set_clock_groups -asynchronous` line for each pair of masters
  whose crossings are all recognized and excepted.

Register cells use `register_pattern` with `/`-separated instance paths. Check
it against the synthesis tool's naming. `spinal_synchronous` lists Spinal
`setSynchronousWith` clock pairs.

The check reads `create_clock`, `create_generated_clock`, `set_false_path`,
`set_max_delay`, `set_multicycle_path` and `set_clock_groups` with
`get_ports|cells|clocks|pins` objects. It reports `sdc.unmatched_clock`
(a clock on a port that is not a toplevel input or no design clock),
`sdc.unconstrained_clock` (a design clock without an SDC clock),
`sdc.unmatched_endpoint` (a cell, pin or port pattern that matches nothing,
including a `create_generated_clock` target that is no design register),
`sdc.generated_mismatch` (a `-divide_by` that differs from the inferred divider),
`sdc.unmatched_multicycle` (a `set_multicycle_path` between registers without a
register path),
`sdc.unsafe_false_path` (an exception or asynchronous clock group that covers an
unsafe crossing) and `sdc.unconstrained_crossing` (a crossing between unrelated
clocks without an exception). Patterns match in both directions: an SDC glob
against concrete names and `register_pattern` against concrete SDC names. A
generated SDC checked against the same design gives no findings (round-trip
test). This checks logical intent against elaborated
endpoints. It is not routed timing signoff and does not read Tcl variables or
loops.

## Reset-domain crossings

`rdc.py` derives reset domains from SpinalDB clock-domain data. A reset domain
is one signature: reset key, kind (`SYNC`, `ASYNC`, `BOOT`), polarity and soft
reset. A register without `init` is in the `none` domain, even in a clock domain
with a reset. The report's `rdc.domains` lists each domain with its reset
source, clocks, register count and release status (`synchronized`,
`unsynchronized`, `synchronizer_stages`, `synchronous`, `boot`,
`not_applicable`).

Each register path between different reset domains gets one class in
`rdc.crossings`:

| Class | Rule | Meaning |
|---|---|---|
| `async_assert_crossing` | `rdc.async_assert_crossing` (error) | The source has an asynchronous reset that the destination does not share. Assertion can make the destination metastable. |
| `resetless_receiver` | `rdc.resetless_receiver` | The destination has no reset. It can capture the source reset value. |
| `independent_reset` | `rdc.independent_reset` | Different synchronous reset signatures, including paths within one clock. |
| `source_not_reset` | none (`no_hazard`) | The source has no reset, so reset cannot change it. |
| `missing_domain` | `rdc.missing_domain` | A register has no clock-domain record. The RDC status is `inconclusive`. |

A path is `protected` only by a project declaration with a reason.
`intent.isolation` rows name `qualifier`, `reason` and `source` and/or
`destination`. The qualifier must be in the destination's combinational
fan-in. Otherwise the check reports `rdc.isolation_unmatched` (error) and keeps
the class finding. `intent.reset_order` pairs `[source reset_key,
destination reset_key]` declare that the destination stays in reset while the
source is in reset. A covered path is `protected` by `declared_reset_order`.
Both are assumptions. They are not proofs of the hardware sequence.

An asynchronous reset is `synchronized` when its net comes, through wires or
inverters, from a chain of at least two one-bit registers in the controlled
clock with a constant first input and an asynchronous reset. This matches
Spinal's `ResetCtrl.asyncAssertSyncDeassert` and `BufferCC` reset bridges.
Otherwise `rdc.async_release_unsynchronized` reports the domain. The chain
stages themselves are `synchronizer_stages`. `rdc.comb_reset_logic` (error)
marks combinational logic with more than one input on an asynchronous reset net.
`rdc.reset_as_data` marks a register that a reset net reaches through data or
control logic. Synchronizer stages are exempt.

`rdc.status` is `findings`, `protected`, `inconclusive` or `no_crossings_found`.
It is never `clean`. Reset trees record each reset control's upstream
combinational cone and stop at registers. Unknown control paths remain
`unknown_control`. Missing typed control identity gets `rdc.unknown_control`.

Waivers are project data with reasons. A waiver that matches no finding in a
backend that ran is stale: it adds a `lint.stale_waiver` error to
`waiver_findings` and sets `stale: true`. A waiver for a backend that did not
run has `stale: null`.

Actual reset ordering, release timing, recovery/removal and functional reset
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
must report `rdc.independent_reset`. Asynchronous controls must report
`rdc.async_assert_crossing` and `rdc.async_release_unsynchronized`.

`Test/runMain spinaldb.LintLibraryFixtures DIR` adds `library`: BufferCC,
StreamFifoCC, PulseCCByToggle, a `ResetCtrl` reset synchronizer and a divided
clock. The extracted test checks their classes, the two bound Gray obligations
and the reset release states.

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
with different reset signatures. A merge whose every cross-reset path is
declared protected (isolation or reset order) is not reported; it is listed in
`rdc.protected_merges`. These checks do not cover arbitrary sequential
latency or memory/blackbox paths. Functional reconvergence remains unrun.

Reset pairs declare source release before destination release. The check accepts
transitive order and rejects unknown reset keys and cycles. An uncovered RDC path
gets `rdc.release_order_unproved`. A covered path is `protected` in
`rdc.crossings`; it does not prove the declared order occurs.
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

## Native connectivity lint

Select `yosys` in `backends` to run `read_verilog -sv`, `hierarchy -check`,
`proc`, and `check`. Rules are `yosys.combinational_feedback`,
`yosys.conflicting_drivers`, and `yosys.undriven`. Other warnings retain
`yosys.warning`. The report keeps the elaborated netlist, native output, script,
wire bits and source attributes. Required outputs are output ports in the RTL.
Undriven outputs and floating used wires are findings. Unused input ports do
not imply a fault. Opaque blackboxes keep the backend inconclusive. Intentional
wired logic needs an explicit RTL resolution model; waivers do not supply it.

## Selected protocol safety checks

Use `rvw lint --protocol protocol.json --out NEW_DIRECTORY --mode prove
--engine abc:pdr --timeout 60 --json`. The manifest is:

```json
{"schema":"rvw.cdc-protocol/1", "kind":"async_fifo", "top":"cdc_fifo",
 "verilog":["sampling.sv","fifo.sv"]}
```

Kinds are `handshake`, `async_fifo` and `reset_release`. Sources must be
self-contained exported RTL. Paths resolve from the manifest. The runner freezes
the sources and checks the exact DUT interface with the native formal flow.
It keeps input hashes, the monitor, native logs and the proof result. BMC is the
default. Select `--mode prove` for an unbounded safety proof. Missing or failed
engines cannot earn a pass. These results do not clear structural findings.

The selected interface uses one global `clk`, active-high synchronous `reset`,
and independent one-bit `source_tick` and `destination_tick` enables. This
explicit event-enable interface is required; a wrapper for real clocks needs
separate review. No clock ratio, fairness or minimum tick rate is assumed.
Transfer designs have one-bit `push`, `pop`, `ready`, `valid`, eight-bit
`data_in` and `data_out`, and three-bit `forward_choice` and `reverse_choice`.
All except ready, valid and data_out are inputs. The handshake monitor permits
one outstanding transfer. The FIFO monitor permits four. An independent queue
checks overflow, underflow, accepted data order and data integrity. Concurrent
send and receive use the old queue state. Empty fall-through is outside scope.
A safety pass does not prove eventual delivery. Activation is `not_measured`;
a DUT that never accepts traffic needs a separate progress/activation check.

Reset designs have the four clock/reset/event inputs and one-bit `source_up`
and `destination_up` outputs. The monitor proves that destination release
follows source release and two destination events. It does not prove physical
recovery/removal or behavior under independent mid-transfer resets.

`SpinalChecks/examples/cdc/` supplies selected implementations. `sampling.sv`
uses per-bit choices between the previous and current digital sample at the
first stage, followed by a second destination stage. Proof leaves all choice
inputs unconstrained. This model can delay a transition and split a multi-bit
transition. It cannot establish analog metastability, voltage, resolution time,
setup/hold, MTBF, placement, or capture of pulses between global samples.
The supplied FIFO uses registered binary state and combinational Gray encoding;
it is not a replacement for the elaborated topology recognizer's registered
Gray encoder requirement. Formal checks inspect the selected RTL directly.

Use `--simulate 1000 --seed 42` instead of formal options to run Icarus with
controlled digital perturbation and independent event enables. Every monitor
assertion is fatal. Success needs the completion marker and a zero exit code.
Missing simulators, timeouts and compile errors remain inconclusive. This is a
seeded simulation result, not a proof. Tests exercise all three correct designs
and faults in held data, FIFO full control and reset release order.

The additional `pulse_capture` monitor drives at most one source pulse after a
free `launch` input. It checks that capture occurs within four destination
events while pending, and rejects duplicate captures. It assumes no clock
fairness; no destination events means no response deadline expires. The DUT
ports are `clk`, `reset`, `source_tick`, `destination_tick`, `pulse`, three-bit
`forward_choice`, and one-bit output `captured`. The wrapper supplies `pulse`.
The correct reference retains a toggle. The fault directly synchronizes a pulse
and loses it when destination events stop during the pulse.

`coherent_bus` uses the four clock/reset/event inputs, one-bit `launch`,
three-bit `forward_choice`, and two-bit output `pair`. Its contract requires
`pair` to equal 00 or 11. The correct reference replicates one synchronized bit.
The fault independently synchronizes both bits and can produce an incoherent
combination under old/new perturbation. This is a selected equal-coded bus
contract, not a general reconvergence proof.

## Same-input comparison harness

Run the pinned ten-case reference suite:

```sh
scripts/with-lock.sh suite nice -n 10 rvw/.venv/bin/rvw lint \
  --benchmark SpinalChecks/examples/cdc/suite.json --out /tmp/cdc-suite \
  --mode prove --engine abc:pdr --timeout 60 --json
```

`rvw.cdc-bench/1` contains nonempty `cases`: unique `id`, `manifest`, independent
`expected` (`pass` or `fail`), and an ordered `source_sha256` list. Hash mismatch
is an input error. Each correct reference has a paired seeded fault. Suite
expectations are the oracle. Neither native nor commercial observations define
the expected result. The runner freezes all sources before execution.

Optional `adapters` rows have a unique `id` (other than `native`) and absolute
executable `command`. Each trusted adapter receives `REQUEST.json RESPONSE.json`.
The request uses `rvw.cdc-adapter-request/1`, with case ID, frozen spec/source
paths, source hashes, monitor path, mode and depth. It omits the expected verdict.
The response must use `rvw.cdc-adapter-response/1`, echo `request_sha256` for the
exact request bytes and `mode`, and report `status` (`pass`, `fail`,
`inconclusive`) plus a nonempty `tool_version`. BMC passes need integer
`reached_depth >= depth - 1`. Timeout, absent output, wrong identity, short BMC
prefixes and malformed responses stay inconclusive. Adapter stdout/stderr stays
in `adapter.log`. The adapter owns tool setup and the translation of this
selected monitor. Inspect its constraints before trusting its observation.

Results use `rvw.cdc-bench-result/1`. Qualification is `matches_on_suite`,
`mismatch` or `inconclusive` per tool. No adapters gives commercial comparison
`not_run`. No licensed tool is bundled. A suite match does not establish
commercial CDC feature parity, general correctness, physical timing or signoff.

### Owned and dated waivers

Select `schema: rvw.lint-settings/2` to require `owner` and `expires` on every
waiver, in addition to the existing exact rule, endpoint, finding_id, config
and reason. `expires` is the last valid UTC date in YYYY-MM-DD form. Missing
metadata or an expired waiver is an error. A waiver that matches no finding
in a backend that ran remains a `lint.stale_waiver` error. An unrun backend
keeps stale null. The metadata and stale-state functions are shared with
generated check dispositions. Version 1 remains a legacy format without an
owner or expiry requirement; no values are invented during migration.
