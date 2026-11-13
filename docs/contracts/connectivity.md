# Connectivity and riscv-formal bindings contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Project connection tables

`rvw.connectivity/1` also accepts CSV and JSON connection inputs. JSON contains
one `connection` array. CSV columns match the TOML row keys. `condition` aliases
`enable`; `delay` aliases `latency`. `inversion` is Boolean and applies to
required transfers only. Conditions are active-high one-bit signal names.
The reverse report inventories undeclared top input influence at declared
destinations, stopping at declared source and condition boundaries. It excludes
clock, reset and initialization edges. Opaque and truncated cones are incomplete.
Per-row `proven` requires an unbounded safety pass and a reachable activation.
`contradicted` requires a required-transfer counterexample and activation.
`bounded_pass` is a campaign observation, never an unbounded proof. Report fields
`unproven` and `contradicted` list row IDs. Overall acceptance remains incomplete.

`rvw soc check --connections TABLE` embeds structural connection results under
`connectivity` in `rvw.soc-check/1`. It retains connection-table and database
SHA-256 values. This option does not launch a solver or change the existing
map/bridge transaction verdict. Missing proof remains an explicit gap.

Required connectivity campaigns can bind internal RTL observations with Yosys
flatten/expose. No driver is cut or replaced. Database RTL paths and widths
must match the flattened netlist. Top port names/types must match. Campaign
`binding` records source hashes, transformed RTL hash and observation aliases.
Internal forbidden influence remains incomplete. The reverse inventory also
checks every top output and reports outputs with no required source declaration.

A proved value contract cannot replace a missing required structural dependency.
Such a row retains its semantic observation but remains incomplete. Native
campaign observations retain and check the child result's proof kind.

Forbidden connectivity activation requires distinct legal source values in the
two DUT copies, sampled with mode/enable and delayed by the declared latency.
A source fixed by assumptions cannot satisfy this witness. Its safety proof
alone remains incomplete. `activation_requirement` states this obligation.

## RVFI binding generation

`rvw.rvfi-binding/1` is project-owned JSON input to `rvw formal rvfi-generate`.
It supplies the DUT top, clock/reset port names, RVFI field port names, auxiliary
input/output widths and the riscv-formal runner settings. Relative RTL and
checker paths resolve against this file. The generated template uses the
upstream `RVFI_OUTPUTS` macro and the runner's `@RVFI_CONNECTIONS@` placeholder.
Auxiliary inputs have independent `anyseq` values. No bus assumptions are added.
`rvw.rvfi-generation/1` reports generated paths, the manifest SHA-256 and limits.
Generation status `generated` is not a proof result.

The riscv-formal runner accepts NRET 1..16 and checks channel-index bounds.
Its cover task includes one retirement cover per channel. Every channel must
reach retirement before bounded passing checks become conclusive observations.
These observations retain the existing C3/C4 limits and cannot accept a core.

## Spinal bridge state probe

`rvw.spinal-state/1` stores an ordered register and memory layout and raw
unsigned decimal values. Restore checks the full layout and value widths before
it writes state through the Spinal simulation bridge. Callers must stop at a
settled low clock. They must restore inputs and all host state before the next
rising edge. This format does not save JVM tasks or Verilator internal state.
It supports synchronous Spinal registers and memories. Blackboxes, latches,
external effects and asynchronous clock domains need separate support.

The project-owned VexRiscv probe uses `rvw.vex-bridge-probe/1`. It stores bridge
state, sparse RAM, pending simple-bus responses, cycle and retirement counters,
trap-handler state and the C2 writer snapshot. It binds the ELF and emitted RTL
and the compiled harness classes with SHA-256. A SHA-256 envelope checks
the saved payload before restore. Its fixed-latency, one-hart RAM harness has no devices or RNG.
This is a native continuation probe, not the general snapshot-port envelope.
## Observed transaction producer

`rvw soc observe` and MCP `soc_observe` generate a read-only simulation
monitor from `rvw.soc-observer/1`. The binding declares data bytes and all
clock, reset, cycle, accepted-request, accepted-response and memory-retirement
signal paths. `reset_active_low` is optional. Paths can name hierarchical
signals and constant array indices. Arbitrary expressions are refused.

`rvw.soc-observed-pins/1` starts a JSONL capture with the binding hash, run ID,
RTL hash, ELF hash and integer seed. Later rows use the request, response and
retirement-link event fields from `rvw.soc-events/1`. Every retirement link
contains one independently sampled transaction tag. Unknown or non-unit
retirement counts stop the simulation. Tags must be unique for the capture.

`rvw soc observe-pack` and MCP `soc_observe_pack` check capture identity
against C1 and package the rows as `rvw.soc-events/1`. The output header also
records the raw pin capture and C2 hashes. The existing pairing checker
compares the events with independent C2 memory effects. Matching samples
remain inconclusive. Generation is not execution. Packaging is not proof.
Core-specific signal bindings and a matching C1/C2 capture remain required.

## RVFI bus environment

`rvw.rvfi-binding/1` accepts optional `bus_environment` and
`environment_constants`. Generated `rvw.rvfi-generation/1` records both.
`stream-response` entries bind `valid`, `ready`, `response`, optional `write`,
`service_bound` and optional `max_pending`. Ports refer to the binding input and
output maps. Environment assumptions bound service and prevent unsolicited
responses. A capacity assertion checks outstanding requests. Constants constrain
input ports only. These restrictions do not establish bus compliance or complete
ISA signoff. Other protocols are refused.

## Unbounded instruction portfolio

`rvw.riscv-proof-capture/1` records upstream prove-mode instruction jobs,
self-contained source hashes and formal input identity. `rvw.riscv-proof/1`
records per-check engine-race results. Bounded and unbounded engine outcomes
retain the portfolio meanings. Source assumptions without activation evidence
keep the campaign inconclusive. These formats grant no ISA signoff.

## ISA kit report

`rvw formal isa` and MCP `formal_isa` write `rvw.isa-signoff/1` to
`result.json`. `rows` carry `check`, `status`, optional `depth`, `reason` and
an evidence path relative to the output directory. `bounded` means only the
specified cycle bound. `proven` requires a successful unbounded portfolio
result under its activation policy. Native failures are `failed`. Timeouts,
unreachable retirement and tool errors remain `inconclusive`. Missing bindings
are `unsupported`. `not applicable` identifies a check covered elsewhere or
excluded by an explicit project scope. Overall status is `fail` on a check
failure and otherwise `inconclusive`; this version does not grant full signoff.

## Machine transition checks

`rvw.machine-checks/1` selects RV32 rules, source files and local signal maps.
`rvw.machine-check-results/1` records per-rule status, depth, native assertion
and cover outcomes, source hashes and limits. Generation gives no proof.
A bounded result needs both assertion PASS and trigger cover PASS. A missing
binding is unsupported. An absent project feature can be not applicable only
with an explicit reason. Source copies are instrumented under the output tree.
The reset assumption is `reset == $initstate`.

## Architectural-state reset and halt

`rvw.architectural-state/1` accepts optional boolean `reset_active_low`, default
false. `signals.halt` is optional. If present, it is a one-bit aligned observation.
Without it, generated RVFI halt remains zero. Trap write suppression and frame
assertions remain in force. A generated map is not an equivalence certificate.

## Sail M expressions and instruction activation

`rvw.sail-m/1` records pinned rule and helper hashes, Sail compiler identity,
final generated model hashes, primitive bindings and backend lowerings. It
covers RV32 M arithmetic only. `formal_isa` adds `instruction_activation` to
instruction rows. A reached activation needs native cover PASS and a trace.
A missing activation changes a passing bounded instruction to inconclusive.
The native cycle settings remain unchanged. Standalone `formal riscv` retains
its earlier general retirement-cover policy.

## Conditional instruction RAM abstraction

`rvw.riscv-abstraction/1` declares module-local pipeline observations, a collected
memory and proof engines. `rvw.riscv-abstract/1` retains the exact single-flight
assumption, original source identity, RAM outcomes, optional RTLIL retry and
concrete conditional cover. RAM word removal is an overapproximation. Failed
abstract models require refinement. The report does not turn them into core
failures. A native engine result remains conditional on the recorded source
assumptions. Overall status is inconclusive unless a concrete failure is known.

`keep_words` is an optional list of concrete word indices. The RTLIL retry
retains those words through the shared word-abstraction function. It preserves
their actual drivers and initial state. `watched` records the active retained
words. `conditional_native_proof` reports a native engine proof under the
recorded abstraction and assumptions. It does not grant full pipeline signoff.
`formal isa --abstraction` exposes these rows with their separate scope.

The ISA signoff table includes missing instruction checks from the declared
upstream ISA list and unselected consistency checks for every retirement
channel. Those rows have status unsupported. Missing inventory is also a gap.
