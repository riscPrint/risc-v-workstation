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
