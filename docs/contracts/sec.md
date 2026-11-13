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

## Case request extensions

`rvw.sec-case/1` requests also carry `observations` (the declared channel
names), `contract_start_pc` and `observer_mode`. A response may name
`c2_keys`, the C2 retirement fields its RTL trace carries. The runner then
checks only those fields against the reference and reports them as
`architectural_keys`. `observer_mode` limits the contract projection, and the
adapter's observations, to retirements in that privilege mode. In
`adapter_command`, `{python}` is the running interpreter.
