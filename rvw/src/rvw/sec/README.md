# Security tests in simulation

`rvw sec` tests digital information flow and microarchitectural leakage.
Timing, caches, speculation, predictors and TLB state are in scope.
Power and electromagnetic leakage are out of scope.
A clean result is `no_leak_observed`. It never means `secure`.
Formal security proofs belong to `rvw formal security`.

## Dynamic information flow

```
rvw sec ift --rtl unit.v --top unit --policy policy.json --stimulus samples.json --out out/ift
```

Policy JSON names `clock`, active-high synchronous `reset`, `sources` and `sinks`.
Sources and sinks name flattened Yosys signals. An internal register can be a source.
A memory is mapped to registers. Name the mapped storage signals as sources.
Bind memory regions and key CSRs to these signals in project data. Automatic address
range decoding is not implemented. For a handshake timing sink, select its valid,
ready or grant signal. For a debug or bus sink, select its observed output signals.
An optional scalar public input `declassifier` permits sink taint while it is high.
This is a sampled release permission. It does not erase taint or prove authorization.

Stimulus is a JSON list of cycles. Every cycle binds every non-clock input to an
unsigned integer. Start with reset high and then release reset. Cycle zero is the
first driven cycle. Sampling occurs after each rising edge and combinational settling.
`--db design.db` maps exact signal names in candidate paths to C6 signal paths.
`report.json` retains policy, sample count, violations and cycles. `results.json`
contains C3 outcomes. MCP tool `sec_ift` uses the same runner.

## Decisions

Reuse the existing Yosys Boolean IFT transform. This supports exported Verilog
from any HDL. A Spinal-only pass would restrict the frontend. The simulation layer
does not change the formal command or its policy. `--mode precise` uses
value-sensitive Boolean transfer functions. This is local precision, not exact
whole-design tracking. `--mode conservative` propagates every gate input taint.
Both modes track mux control and sequential state. Clocks must be public.
Unsupported cells cause an error. Native commands have bounded time limits.

## What this technique can show

A tainted sink identifies potential secret influence under the supplied stimulus.
The result gives a cycle and a structural candidate path. It does not reconstruct
dynamic provenance. A C6 match is name based. It does not establish a complete
source-level path. Reconvergence can cause false alarms in both modes.
There is no proof of whole-core noninterference, declassification authorization,
reset coverage or hardware security. Verilator uses two-state simulation. The
caller must reset all relevant state before observation. No physical model runs.

## Tests

`rvw/.venv/bin/python -m pytest rvw/tests/test_sec.py -q` runs small Verilog designs
with a planted leak and a fixed control. No BOOM simulation is needed.

## Architectural contract pairs

`rvw sec contract --manifest pair.json --out out/pair` runs two independent RTL
cases and reduces a witnessed difference. MCP tool: `sec_contract`.
A manifest declares `contract`, `clauses`, `observations`, `public`, `secrets`
(two different JSON values), `seed`, `instructions`, and `adapter_command`.
The command generates a seeded public ALU instruction list. A project can supply
its own `program` list with loads, branches and transient operations instead.

```
{"contract":"constant-time", "clauses":["pc","memory","branch"],
 "observations":["cycles","cache","branch","tlb","bus"],
 "public":{"reset":"cold"}, "secrets":[0,1], "seed":7, "instructions":16,
 "adapter_command":["python3","adapter.py","{request}","{out}"]}
```

The adapter receives `rvw.sec-case/1` JSON. It must compile and run the program
with its declared secret binding. It writes `response.json` with `complete: true`,
`reset_complete: true`, `reference_c2`, `rtl_c2` and `observations`.
C2 paths are relative to the case output directory. The reference must come from
an independent Spike run or equivalent trusted ISA model. The tool checks
complete C2 traces and architectural agreement for each case before comparison.
Adapters can convert `rvw.probe-events/1` cache, branch and TLB samples into
observation arrays. Keep cycle and bus samples in these arrays when relevant.
The adapter owns reset, probe placement, receiver sampling and ELF generation.

The contract names are `constant-time`, `sandboxing` and
`speculative-constant-time`. Clauses select retired PCs, memory addresses and
branch outcomes. The name records intent. A name alone does not emulate
speculation or prove sandbox access policy. The project program and independent
reference implement those semantics. This flow compares RTL transient samples
within equal architectural traces. It does not infer transient observations
from the reference. This follows the equal-contract-class approach used by
Revizor. It is not an implementation of Revizor, SpecDoctor or TheHuzz.

The reducer deletes instructions and reruns both cases. It keeps a deletion only
when the contract is still equal and the leak persists. `minimize_runs` bounds
trials and defaults to 16. The witness is not necessarily a global minimum.
Missing or mismatched evidence gives `inconclusive`. No eligible comparison also
gives `inconclusive`. Adapter claims and external tool dependencies are trusted.
No native whole-core campaign has been run for this interface.
