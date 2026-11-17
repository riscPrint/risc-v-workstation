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
Trap signals can be top-level ports or internal signals. `cause` is optional
(0 when absent). An optional `epc` gives the PC of a trapped instruction that
the commit port does not report; the C2 trace then gets that instruction.
A commit-kind core declares only `pc` and `insn` as checked C2 fields.
`link` (linker script, default `../programs/link.ld` relative to the binding)
and `march` (default `rv32im_zicsr`) select how `rvw.sec.core_adapter` builds
case programs. A bus with `latency` 0 is a same-cycle (asynchronous RAM)
port: the testbench answers `rsp_data` from the current `cmd_address` before
each edge and queues nothing. Such a bus needs no `rsp_valid` and must not
name `cmd_ready`.
A bus with `burst: true` (cache refill ports) answers a read of `2^cmd_size`
bytes as word beats from the size-aligned base, one beat per cycle after
`latency`; a write is one beat. Optional `rsp_last` marks the last beat.
A commit-kind `retire` may name `mode`, an internal privilege signal sampled
at each commit; `mode` is then also a checked C2 field.

## Run binding for C1 adapters

`rvw.sec-run/1` is project data for `python -m rvw.sec.run_adapter`. It names
`name`, `adapter` (argv; a relative first element is relative to the file),
`platform` (Spike platform JSON), optional `config`, `run_args` (appended to
`run`), `link`, `march` and `timeout`. The adapter runs
`ADAPTER run --elf ELF --out DIR --rvfi-trace --probes --json [--config C] ARGS`
and reads `DIR/result.json` (`status`, `cycles`), `DIR/rvfi.jsonl` (C2) and
`DIR/probe-events.jsonl`. The C2 trace is cut after the first store to
`tohost` (`DIR/cut.jsonl`), like the Spike reference. Observation channels are
`cycles`, `retire_cycles`, the probe event channels and `probe_counters`
(whole-run totals). Bus channels are an error.

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
lists of `{cycle, kind, name, field...}` with window-relative cycles (cache
events without their `data` field: line contents are architectural data, not
a side channel);
`probe_counters` is `{name: total}`; `bus_handshakes` is a sorted list of
`[cycle, bus, "cmd"|"rsp"]`.

## Leakage campaign state and results

`rvw sec campaign` keeps `state.json` (`rvw.sec-campaign/1`): `iteration`,
`pairs`, `seconds`, `corpus` (program, secrets, pair, new coverage keys),
`coverage` (sorted keys), `signatures` (key: `signature`, `first_pair`,
`count`, reduced `program`, `secrets`, `contracts`), `statuses` and `errors`.
A signature is the reduced program's sorted mnemonics and the differing
channels, `MNEMONICS|CHANNELS`. `results.json` has one C3 `fail` per signature
(`signature` `sec:campaign:...`), else one `pass` when at least
`min_eligible_pairs` pairs were eligible, else an `error` with `inconclusive`.
`min_eligible_pairs` is `ceil(min_eligible_fraction × pairs)`, at least 1; the
manifest key `min_eligible_fraction` defaults to 0.5. `report.json` gives
`eligible_pairs`, `min_eligible_pairs` and `pairs`. Below the minimum, a
campaign without a signature is `inconclusive`, not `no_leak_observed`. Each pair keeps its paired
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

## Mapped init binding

Mapped RV32 req/rsp init with RVFI emits `rvw.sec-core/1` under `rvw/sec`.
It translates declared bus roles without guessing signal names. The default
native environment supplies one-cycle responses and active-high reset.
`rvw/export-rtl.sh` exports simulation elaboration to `rvw/out/export/core.v`.
The sample pair and flow policy are bounded examples. They are not qualification.

## Finite core-flow preparation

The ift-core timeout covers native netlist generation, shadow compilation and
simulation in one wall budget. The default is 110 seconds. Progress goes to
stderr and progress.json. A native timeout returns rvw.sec/1 inconclusive with
the last phase and available cell/byte counts. Counts describe preparation
cost. They do not predict runtime. Keep the work cache to reuse completed work.
Scaffolds include flow.S, a short load from the declared scratch word.

## C1 pair adapter

`python -m rvw.sec.c1_adapter` is an adapter for the existing `rvw sec contract`
command. Its `--binding` file uses `rvw.sec-c1/1`. Required fields are `platform`,
`adapter`, `config` and `link`. Paths are relative to the binding file.
`name` supplies the reference trace core label. The platform selects XLEN and
ISA. The compiler uses ILP32 for RV32 and LP64 for RV64 integer programs.

The template has `RVW_SETUP`, `RVW_PROGRAM` and `RVW_DATA` markers. It declares
`case`, `case_end` and `tohost`. Setup has a fixed instruction count for each
XLEN. RV64 setup retains all 64 secret bits. Put an initial instruction in the
case window before the operation whose latency must be measured.

Only `cycles` and `retire_cycles` observations are supported. Both come from
observed C2 retirements between the two case symbols. Each side needs C1 pass,
input closure and a complete strict Spike match with no masks or synchronization.
The raw C2 trace stays intact. The adapter then writes a security trace through
the actual passing `tohost` store. This omits post-completion drain instructions.
The independent generated reference uses the same completion boundary. A missing
or failing store is an error. No DUT register or memory value comes from the
reference. The response records both raw and scoped trace paths.

## Paired model identity

A case response may supply `rtl_identity`. If either response supplies it,
the two values must match. A mismatch makes the pair inconclusive before
contract comparison or reduction. Older adapters can omit the field on both
sides. This does not establish model identity.

The direct core adapter supplies the SHA-256 of the simulator executable.
This binds the compiled RTL and testbench used for the run. The C1 run adapter
forwards `result.json`'s `rtl_sha256` when available. These identities have
adapter-specific meanings. They do not establish whole-core qualification.
