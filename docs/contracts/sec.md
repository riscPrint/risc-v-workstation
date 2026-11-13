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
