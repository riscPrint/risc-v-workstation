# Simulation security

## Digital observations

`rvw.sec/1` reports `violation`, `no_leak_observed` or `inconclusive`.
It records the technique, findings and evidence completeness. A clean C3 test
means no leak was observed in this bounded sample. It is never a security proof.
IFT findings record cycle, sink, structural candidate path and matched C6 paths.
Sources, sinks, reset, release permission and stimulus belong to the project.
Physical power and EM channels are outside the contract.

## Paired program adapter

`rvw.sec-case/1` requests contain a program instruction list, secret, public
context and contract name. Responses confirm reset and completion, name complete
independent-reference and RTL C2 paths, and bind every declared microarchitectural
channel in `observations`. Equal public context and architectural contract traces
are prerequisites for a leakage comparison. A minimization trial must rerun both
cases. Unavailable or mismatched evidence cannot earn a clean result.

## Unit latency

Unit manifests bind scalar public clock, active-high synchronous reset, start
and done. Operand pairs bind all data inputs and vary only declared operands.
Samples count rising edges from a one-cycle start pulse to first done, after two
reset cycles. Missing completion is inconclusive. Operation names are declarations,
not independent instruction decoding evidence.

## Isolation observation window

Isolation manifests declare isolation_kind, boundary, policy and contract_start_pc.
The reference contract starts at the first occurrence of that PC. The adapter
must restrict microarchitectural samples to the same post-boundary window.
Setup remains subject to complete per-case RTL/reference architectural agreement.

## Security faults

Security fault campaigns reuse rvw.fault-plan/1 and single-cycle flip events.
Each C1 adapter run also writes security-observations.json with exactly the
manifest's digital channel names. A harmless architectural trace requires equal
security observations. A declared named detection can satisfy the detection
check. Generic fail/assert statuses without declared names remain unresolved.

## Aggregate outcomes and generated gadgets

sec suite accepts only executed rvw.sec/1 reports. It emits one C3 test per
report. Missing or invalid reports produce error entries. Violations survive
incomplete peer results. Completeness retains every child report's completeness.
The rvw.sec-gadgets/1 generation manifest names four assembly templates, expected
no-leak outcomes, a register ABI and project environment hooks. It is generated
evidence only. It cannot earn an executed C3 pass.

IFT reports checked_cycles. Zero enabled sink samples is inconclusive. Optional
C6 dependency paths retain query capture identity and structural-path limits.

## Boolean unknown constants and reset support

IFT treats X/Z constants as unknown Boolean values with taint set. Reports name
this policy in `unknown_constants`. Z does not model electrical high impedance.
Unsupported state cells refuse instrumentation before native simulation with a
hint to rebuild every flow from the same project-owned SYNC elaboration entry.

## Core binding for native runs

`rvw.sec-core/1` is project data. It names `rtl` (Verilog paths; environment
variables allowed, relative to the file), `top`, `clock`, active-high `reset`,
`reset_cycles`, `ram` (`base`, `size`), `max_cycles`, the Spike `platform` JSON
and `buses`. Each bus has `name`, `kind` (`fetch` or `data`), `latency` and the
port names `cmd_valid`, `cmd_ready`, `cmd_address`, `rsp_valid`, `rsp_data`, and
optionally `cmd_write`, `cmd_data`, `cmd_mask` or `cmd_size`, `cmd_id`,
`rsp_error`, `rsp_id`, `write_response`. Responses come in request order after
`latency` cycles. Data is read when the command is accepted. Other inputs are
tied to zero or to `ties`. `retire` is `{"kind":"rvfi","prefix":...}` (RVFI
ports) or `{"kind":"commit","valid":...,"pc":...}` (internal commit signals).
`trap` optionally names `valid`, `cause`, `tval` and an internal `privilege`.
A commit-kind core declares only `pc` and `insn` as checked C2 fields.
`link` (linker script, default `../programs/link.ld` relative to the binding)
and `march` (default `rv32im_zicsr`) select how `rvw.sec.core_adapter` builds
case programs. A bus with `latency` 0 is a same-cycle (asynchronous RAM)
port: the testbench answers `rsp_data` from the current `cmd_address` before
each edge and queues nothing. Such a bus needs no `rsp_valid` and must not
name `cmd_ready`.

## Case request extensions

`rvw.sec-case/1` requests also carry `observations` (the declared channel
names), `contract_start_pc` and `observer_mode`. A response may name
`c2_keys`, the C2 retirement fields its RTL trace carries. The runner then
checks only those fields against the reference and reports them as
`architectural_keys`. `observer_mode` limits the contract projection, and the
adapter's observations, to retirements in that privilege mode. In
`adapter_command`, `{python}` is the running interpreter.

## Probe observations from native runs

A native run writes `probe-events.jsonl` in `rvw.probe-events/1` when the RTL has
SpinalProbes wires or the binding declares `events` (`kind`, `name`, `valid`,
`fields: {field: [signal, width]}`, optional `meta`). `probe_meta` maps
`KIND:NAME` to the probe's elaboration metadata. The stream ends at the cycle of
the retirement of the `tohost` store, like the C2 trace. Case observation
channels `branch_events`, `cache_events`, `tlb_events` and `probe_events` are
lists of `{cycle, kind, name, field...}` with window-relative cycles;
`probe_counters` is `{name: total}`; `bus_handshakes` is a sorted list of
`[cycle, bus, "cmd"|"rsp"]`.

## Leakage campaign state and results

`rvw sec campaign` keeps `state.json` (`rvw.sec-campaign/1`): `iteration`,
`pairs`, `seconds`, `corpus` (program, secrets, pair, new coverage keys),
`coverage` (sorted keys), `signatures` (key: `signature`, `first_pair`,
`count`, reduced `program`, `secrets`, `contracts`), `statuses` and `errors`.
A signature is the reduced program's sorted mnemonics and the differing
channels, `MNEMONICS|CHANNELS`. `results.json` has one C3 `fail` per signature
(`signature` `sec:campaign:...`), else one `pass` when at least one pair was
eligible, else an `error` with `inconclusive`. Each pair keeps its paired
`report.json` under `pair-NNNN/run`, and its reduction under `pair-NNNN/reduced`.

## Automatic IFT bindings

An `ift-core` policy entry `{"soc_region": NAME}` (optional `offset`, `size`
or `register`) resolves to `{base, size, soc_region[, register]}` through a
`rvw.soc/1` map. `csrs` lists catalog CSR names or addresses; each resolves to
one design netname, or the binding's `csr_signals` map gives it. The
`rvw.sec/1` IFT report adds `csrs` (name to netname), the resolved
`memory_regions` and `tainted_memory` (`words`: tainted RAM words at the end;
`propagated`: up to 64 `[address, mask]` words outside the secret regions).

## Model pre-check manifest

`rvw sec model-check` manifests name `contract`, `clauses`, `binding` (for the
template, link script and Spike platform; RTL is not needed), `template`,
`model` (an `rvw.arch-core/1` description or an `ooo` table), `program`,
`secrets` (two) and `operand_latency` (class to rule: `fixed` `latency`;
`quotient_bits` `base`, `per_bit`; `early_out` `operand`, `width`, `short`,
`long`). The `rvw.sec/1` report (`technique` `model-precheck`) records each
case's `predicted_cycles` and rule latencies, and `evidence` states that it is
a model prediction, not RTL evidence.

## Missing evidence and positive results

Security suite completion requires conclusive child outcomes and complete evidence. Canonical verdicts must agree with technique status. A selected observer needs reference retirements in both runs. Missing observer data yields `inconclusive`. A conclusive violation remains a failure even when another technique is incomplete.
