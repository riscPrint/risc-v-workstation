# Native source coverage sample

Four physical ISA programs (`add`, `beq`, `lw`, `sw`) passed C1 and complete
strict Spike comparison. Each program uses a fresh simulation with seed 1.
No masks or synchronization were used. The private locks are `vex-dv` and
`sbt-dv`. `RISCVSIM_COVERAGE=line,toggle` selects the native metrics.

| Metric | Hit | Total | Holes |
|---|---:|---:|---:|
| branch | 615 | 774 | 159 |
| line | 701 | 831 | 130 |
| toggle | 26329 | 31098 | 4769 |

The add baseline hits 27074 points. The four-program union hits
27645 points. The added workloads close 571 holes.
Six closed points have Scala source links. The full native denominator stays
32703. Only 586 points have source links.
The rest remain unmapped. No Scala statement hit is inferred.

The source report (historical counts and regeneration command in the example README) keeps line/toggle/branch metrics and
functional groups separate. Functional links to the ALU source line are
project declarations. They are not measured statement attribution.
The report emits native `code_targets` and semantic `functional_targets`.

The initial native holes drive `rvw cov closure` suggestions. Candidate
signatures come from these same four measured workloads. The best additional
workload is `rv32ui-p-lw`. It targets
546 initial holes. This is measured suite
guidance. It is not a held-out prediction or an adaptive generator campaign.
The controller's native code-feedback receipt remains a separate obligation.

[The measurement](measurement.json) records input hashes and point identities.
Raw C1, C2, DAT, functional reports and candidate signatures remain under
`rvw/out/dv/source-vexiiriscv` in the worker checkout. Path aliases in these published records are
for display. The source-report hash pins the original raw report.

To make a new report, run the example adapter with `--rvfi-trace --coverage
--probes`, seed 1 and zero memory latency. Qualify its full C2 trace with
`rvw cosim check --strict`. Merge its C1 paths with `rvw cov merge`. Generate
functional coverage from the same traces and the project's ISA manifest.
Then run `rvw cov source-report --database code.json --functional
functional.json --bindings source-bindings.json --json`. Bind exact native
source lines and fixed functional groups as described in the coverage README.

These results do not grant C4 acceptance or whole-core qualification.

A fresh guided replay matched all 321 instructions against Spike.
It closed 546 initial native holes. No masks or synchronization
were used. The replay uses the characterized workload and seed.

Historical `source-report.json`: {"status":"reported","point_universe":"46ff39b8fe06141c5ac512acfe278769a49f5e825086e5a7a2cda6b1348ce7b6","lines":{"records":356},"code_targets":{"records":5058},"functional_targets":{"records":2},"unmapped_native_points":32117,"unmapped_functional_groups":{"records":239},"native_source_states":{"entries":1},"notes":{"records":4}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov source-report --database code.json --functional functional.json --bindings source-bindings.json --json`. Use the pinned inputs and options from [PR #1022](https://github.com/riscPrint/risc-v-workstation/pull/1022).
