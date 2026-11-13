# Clean-room acceptance, 2026-11-13

This test used a new six-phase multicycle RV32IM core named Stepper. The core
has one outstanding memory transaction. It now completes split-word loads and
stores through two transactions. Its source has 255 Scala lines. It is
in its own Git repository under `wt/.cleanroom/core`, outside the workstation.
No earlier scratch core was copied.

The initial workstation revision was `ec7126c3`. The final measured revisions,
counts and timing are recorded below. The full journal, stdio client, command
logs and JSON receipts remain under `wt/.cleanroom`. Scratch RTL, ELFs, databases,
waves and native build output are not part of this change.

## Result and scope

All 50 programs passed on RTL: 42 RV32UI and eight RV32UM. All 50 strict Spike
comparisons matched. There were zero mismatches, inconclusive comparisons or
synchronization allowances. The C1 records contain 14,408 retirements in 73,662
summed test cycles. Every final C1 source record has core_dirty=false and
tools_dirty=false.

Time from the empty Git repository to the complete result: **2,192.673 seconds,
or 36 minutes 33 seconds**. The start is the filesystem creation time of
`.git/config`, 2026-11-13T14:43:13.714205+00:00. The end is the saved completion time of the
full reference report, 2026-11-13T15:19:46.387295+00:00. This includes core writing,
debugging, workstation fixes, validation and waits. It is not simulator time.
The final regression call took 16.713 s. The full reference call took 76.980 s.

Core revision: `384e6775472c89f02472147df4c5690a319659f0`. Tested workstation revision:
`efa97530abe8c5dddbc397e38a0a4a8694a05920`. That committed snapshot predates the documentation
branch rebase. Source fingerprints remain in the raw C1/C3 receipts.
The riscv-tests source pin is `d7e86f701b929b5d801f8cda1a4871ab05f452bb`.
Core Scala SHA-256: `c6e53e11d9617d70f1905c0148e76c5cfa994f341d58a7d62dd79931be5bd69c`.

The test environment preserves all 42 RV32UI and eight RV32UM instruction test
bodies. It replaces the privileged startup with a project-owned direct-tohost
environment. Thus these results qualify that instruction test environment.
They do not qualify upstream privileged boot, interrupts, PMP, exceptions or
whole-core ISA conformance. No test was filtered out or waived.

## Method and limits

Before the comparison phase, the test used only the three permitted guides,
`rvw agent guide`, command help, generated core-project files, and stdio MCP.
The client started with `--profile core`. It found and loaded other profiles
through `rvw_tools_search`, `rvw_tools_describe` and `rvw_tools_load`.
Long MCP jobs stayed in the same server session until their results arrived.
The client saved the returned envelope and wall time for each call.

The earlier report was first read after every requested tool family had an
attempt or a recorded binding/schema blocker. No earlier scratch journal or
core was read. Workstation implementation reads started only after that boundary.
The integration guide itself exposed historical result tables. The final
repair reruns are informed reruns, not a second independent newcomer trial.

There were procedure deviations. Query discovery overlapped an ISA retry, so
this was not a fully serial walk. Early MCP calls did not explicitly inherit
nice priority. Later calls inherited `nice -n 10`. One gate and one suite were
invalidated by changes made while they ran. They remain in the journal and are
excluded from acceptance evidence. Native build commands used nice priority 10
and private `sbt-cosim`. At most two owned simulations or proof jobs ran together.
No subagent was started. Disk checks stayed above 15 GiB free.

## Step scores and wall times

The four scores are `smooth`, `worked after one doc lookup`, `needed guessing`
and `blocked`. A score describes setup and use. It is separate from the result.
For example, a smooth fault campaign can correctly remain inconclusive.
Times below are observed call or command wall times in seconds. MCP times
include server startup and result retrieval. They exclude design editing.
The journal retains all failed attempts and grouped command times.

| Step | Before fixes | After fixes | Wall time and result |
|---|---|---|---|
| Install check / doctor | worked after one doc lookup | worked after one doc lookup | Initial group 8.891 s. Stale shim rebuilt with the documented command. Native presence was not conformance. |
| Init | needed guessing | smooth | Three CLI attempts, about 0.44 s each. Bus role names were absent from help. A new scaffold recheck used the complete mapping. MCP init still lacks mapped options; the guide states the CLI path. |
| Adapter / RVFI build | needed guessing | smooth | Initial build 31.255 s, then 19.136 s with the manual marker. New generated runtime source removes the missing class directory. Fresh scaffold smoke: 102 cycles, 15 retirements. |
| First ELF | worked after one doc lookup | smooth | First native smoke: 105 cycles, 15 retirements. My register assignment overlap was a core error. |
| RV32UI / RV32UM regression | smooth | smooth | First 38.192 s: 48/50 pass. Own divide fix: 61.022 s, 49/50 pass. Final regression 16.713 s: 50 passes. |
| Spike comparison | needed guessing | worked after one doc lookup | First suite 120.887 s: 40 match, nine observer-address mismatches, one C1 fail. Completed split RAM needs the explicit guarded opt-in. Final comparison 76.980 s: 50 matches. |
| Planted-bug bundle | blocked | smooth | 1.609 s missing debug.config; 1.035 s after recipe. C5 records the native assertion. No wave or rerun requested. |
| Committed gate accept / reject | needed guessing | smooth | Frozen repeat 50.604 s: accept, one smoke test. Fault 38.507 s: reject, one new assertion. The earlier moving-source gate is excluded. |
| Bisect | blocked | smooth | 1.185 s missing debug.config; 50.909 s after recipe. Both endpoints tested. First bad is b780198. The commits are adjacent, so no interior search was needed. |
| Database / query | worked after one doc lookup | worked after one doc lookup | query_build_db succeeds; initial extraction 1 component, 138 signals and 465 dependency edges. Query info 1.269 s. This database predates the split-memory change. |
| Probes / perf | needed guessing | worked after one doc lookup | Conversion 1.207 s; perf 1.004 s. Mapped --konata is unsupported. Offline conversion works. The stream has 14 retirements, one open ID; C1/C2 have 15. |
| Coverage | smooth | smooth | Functional report 1.290 s on 15 retirements. Native structural merge 1.099 s. No closure or source-statement coverage claim. |
| checks plan | blocked | smooth | MCP TypeError before fix; stdio rerun 0.899 s returns requirements. CLI had worked. |
| checks generate --all | blocked | worked after one doc lookup | Missing manifest before recipes. Valid signal binding generates control_range in 1.277 s. Other families remain unbound. Native monitor execution NOT RUN. |
| Scala property DSL | worked after one doc lookup | worked after one doc lookup | Explicit SpinalChecks dependency required. Successful sbt emission took 4 s. One write-implies-request assertion emitted. Native assertion execution NOT RUN. |
| formal isa | blocked | blocked | 1.875 s initial report. All instruction/state/conformance rows unsupported; aggregate inconclusive. No ISA kit binding was created. |
| Formal autocheck | blocked | worked after one doc lookup | Empty manifest error clarified. Valid depth-6 event-model call 2.960 s: mode=3 reached. Aggregate inconclusive. This is a constant output observation, not an instruction proof. |
| Lint | blocked | worked after one doc lookup | Valid structural settings: 0.907 s, one active finding and inconclusive structural status. Database and later simulation are different elaborations; no signoff claim. |
| Fault | smooth | smooth | Sites 1.600 s, 1551 bits in the initial database. Campaign 18.588 s: one confirmed pc injection, one timeout, overall inconclusive. No detection or reliability claim. |
| Security | blocked | blocked | Initial bare observations KeyError. Rerun 1.300 s names adapter_command, observations and the guide. No paired DUT adapter exists. Native security NOT RUN. |
| Arch build / what-if | blocked | worked after one doc lookup | arch_build needs project workload/model paths. Timing recipe reports model-only results in 0.949 s. No gem5 execution or RTL speedup claim. |
| SoC compose / verify | blocked | blocked | Compose 1.036 s emits 11 files around the idle wrapper. Verify 1.149 s reports consumer bindings and actions. Own CPU wrapper and native SoC execution NOT RUN. |
| UVM / VIP scaffold | blocked | blocked | 0.922 / 0.962 s. Both refuse the untyped bus and request explicit bindings. No native bench on Stepper. |

## What changed in the workstation

- [#1202](https://github.com/riscPrint/risc-v-workstation/pull/1202): remove the internal job argument from short MCP check planning. The registry test failed first, then five plan tests passed.
- [#1204](https://github.com/riscPrint/risc-v-workstation/pull/1204): generate a runtime Scala object for mapped adapters. Eleven init tests passed. A second empty project compiled and ran without a handwritten marker.
- [#1209](https://github.com/riscPrint/risc-v-workstation/pull/1209): document project input recipes, bus roles, memory conventions, debug setup and optional manifests. Remove stale planned-command text. Final guide/init tests passed.
- [#1211](https://github.com/riscPrint/risc-v-workstation/pull/1211): replace bare manifest field errors with required inputs and setup actions. All three new tests failed first. Seven targeted tests then passed.
- [#1214](https://github.com/riscPrint/risc-v-workstation/pull/1214): document the existing guarded scalar_split_ram policy in the permitted guides. The first full comparison refused ma_data without it. A strict single-trace rerun matched after the reviewed platform declaration.

These fixes did not change the core's instruction results. Separate core commits
corrected division overflow, RVFI address convention and split-word execution.
No exception, synchronization or failing test was waived.

## Compare with the four earlier passes

Confirmed for this new integration: installed CLI/MCP discovery, source and RTL
identity capture, classpath reuse after startup, committed smoke accept/reject,
query extraction, coverage merge and unresolved fault status. SoC verification
names binding keys and actions. VIP commands exist.

The earlier fixes are not all newcomer-discoverable from the three guides.
Completed split RAM worked only after finding its opt-in outside those guides.
Debug setup also needed a complete recipe. The mapped empty class directory and
MCP check-planning crash were new failures.

Bus bridges, typed VIP bindings, whole-core formal state and complete probes
remain project work. The earlier interrupt, predictor and arithmetic partition
results were not exercised by this core. They are not reconfirmed here. The
older report's successful real CPU SoC is not evidence for Stepper's idle scaffold.

## Remaining blockers, in order

1. Whole-core formal and observer conformance. No reviewed ISA/state kit exists
   for Stepper. The emitted check and reached constant mode do not close this.
2. Native SoC and UVM integration. The custom bus needs a wrapper, a supported
   protocol contract, exact pins and independent consumers. Generated idle
   sources do not run the CPU.
3. Native security binding. A paired-secret adapter and observation contract
   are missing. The C1 launcher does not supply them.
4. Probe endpoint accounting and generated-check execution. One final retirement
   is absent from probes. The control-range monitor and Scala assertion have not
   run on RTL. Performance causal completeness is not established.
5. Advanced setup coverage. Mapped MCP init, a core-owned formal kit recipe,
   custom VIP pin recipes and gem5 workloads still require more project work.
   The final recipes were not tested by another independent newcomer.
6. Existing documentation-site staging failure. Every fast set reported
   test_docs_site.py::test_docs_staging_does_not_write_sources. It is outside
   these fixes. Full Python, BOOM, long proofs, CI waits and physical work were
   NOT RUN.

A new core project can rely on the installed interface for finite native
instruction runs, recorded RVFI comparison, committed smoke gates, failure
reports, bisection, database queries and coverage collection after explicit
mapping and input review. It can use optional tools to expose binding gaps.
It cannot rely on init to infer its bus semantics, complete security/formal
contracts, integrate a real SoC, or qualify a UVM bench. This run does not earn
whole-core, hardware or release qualification.

## Validation

Fast sets before pushes: 2886, 2926, 2927, 2941 and 2948 passing tests respectively;
one skip each, with the existing documentation-staging failure. The first guide
run also caught a new shell-continuation parsing error; it was fixed before push.
The final guide/init selection had 14 passes. Initial recipe/release selection
had 52 passes. Final split-guide and report checks are recorded with their PRs.
The hot command reference, roadmap and TODO were not changed. Rebases had no
conflicts, so union-rebase.sh was not needed. No CI wait was used.

The report validation passed 42 release-hygiene and guide checks. Its final fast
set had 2,949 passes, one skip and 8,076 deselected tests. The one failure was
the same documentation-staging test named above. Final disk check had 25 GiB
free. Retained scratch data is about 424 MiB, mainly JSON receipts and C2 traces.
No waves or Verilator build trees were written to `/private/tmp`.

## Second pass: generated native bindings

This is an informed implementation rerun on the same Stepper core. It is not
another independent clean-room trial. The worker read workstation code to fix
the gaps. Native commands used the new guides, generated inputs and command
help. The original 50/50 regression and strict comparisons were not repeated.
Those counts remain historical evidence from the first pass.

The generic changes are separate small PRs: mapped MCP init
[#1222](https://github.com/riscPrint/risc-v-workstation/pull/1222), security
[#1224](https://github.com/riscPrint/risc-v-workstation/pull/1224), formal ISA
[#1225](https://github.com/riscPrint/risc-v-workstation/pull/1225), CPU SoC
[#1227](https://github.com/riscPrint/risc-v-workstation/pull/1227), and live
pyuvm/VIP [#1229](https://github.com/riscPrint/risc-v-workstation/pull/1229).
Probe endpoints, declaration stubs and shim diagnostics are in
[#1230](https://github.com/riscPrint/risc-v-workstation/pull/1230).
No Stepper source was committed to the workstation. The new scratch project
inputs were uncommitted during these functional runs. No gate acceptance or
release qualification is claimed.

Scores below describe setup. `NOT RERUN` means that the earlier score is
retained without new runtime evidence. The new scores are provisional because
the implementation worker knew the changes. They do not establish how a new
independent agent will perform.

| Step | Earlier after-fix score | Second-pass score | New result |
|---|---|---|---|
| Install check / doctor | worked after one doc lookup | smooth | Stale shim diagnostic gives the exact rebuild command. Shim rebuilt during bench setup. Presence does not qualify the core. |
| Init | smooth | smooth | Mapped init through stdio MCP: planned, exit 0, 0.819 s. Bus roles and RVFI options reach the generator. Dry run did not overwrite the project. |
| Adapter / RVFI build | smooth | smooth | Shared export entry compiled and emitted Stepper RTL. Native probe rerun also compiled the changed adapter. |
| First ELF | smooth | smooth | New direct pyuvm smoke: 15 live Spike-checked retirements and passing tohost. |
| RV32UI / RV32UM regression | smooth | smooth | NOT RERUN. Earlier 50 passes retained. |
| Spike comparison | worked after one doc lookup | worked after one doc lookup | NOT RERUN as a suite. New finite live scoreboards passed. The guarded split-memory platform choice remains explicit. |
| Planted-bug bundle | smooth | smooth | NOT RERUN. |
| Committed gate accept / reject | smooth | smooth | NOT RERUN. New dirty functional runs do not earn acceptance. |
| Bisect | smooth | smooth | NOT RERUN. |
| Database / query | worked after one doc lookup | worked after one doc lookup | Existing database used for top validation. Extraction NOT RERUN. |
| Probes / perf | worked after one doc lookup | smooth | Direct mapped --konata: 15 retired events, zero open IDs. C1 and C2 each have 15 retirements. The terminal native regression passed in 8.40 s. |
| Coverage | smooth | smooth | NOT RERUN. |
| checks plan | smooth | smooth | Stdio MCP returned the plan in 0.872 s. Rule rows include declaration templates. |
| checks generate --all | worked after one doc lookup | worked after one doc lookup | Review-only signal-role and Scala declaration stubs are generated. Remaining families need actual semantic bindings. Monitor execution NOT RUN. |
| Scala property DSL | worked after one doc lookup | worked after one doc lookup | NOT RERUN. |
| formal isa | blocked | worked after one doc lookup | Generated kit ran instruction and cover checks. Per-check results follow. No machine-state or observer conformance proof. |
| Formal autocheck | worked after one doc lookup | worked after one doc lookup | NOT RERUN. |
| Lint | worked after one doc lookup | worked after one doc lookup | NOT RERUN. |
| Fault | smooth | smooth | NOT RERUN. |
| Security | blocked | worked after one doc lookup | Generated pair completed two native runs: no_leak_observed. Precise and conservative flow trials each reached the 115 s preparation limit. No flow verdict. |
| Arch build / what-if | worked after one doc lookup | worked after one doc lookup | NOT RERUN. |
| SoC compose / verify | blocked | worked after one doc lookup | Real Stepper wrapper elaborated. Composed smoke: 15 matches. RAM-mailbox Hello, world!: 80 matches. Verify consumer closure remains missing. |
| UVM / VIP scaffold | blocked | worked after one doc lookup | Generated live pyuvm bench passed. It used Python 3.13, cocotb 2.1 and pyuvm 4.0. Python 3.15 was refused by cocotb. No second bus binding was written. |

### Formal per-check results

The scaffold selected add, load, store and retirement cover at depth 24.
The per-check wall limit was eight seconds. The memory binding used stable
symbolic bytes, ordered writes and one-cycle read responses. All selected
instruction checks reached their native engines. No handwritten ISA wrapper
was needed. The result is not a proof of that memory environment on hardware.

| Check | Depth | Result | Instruction activation |
|---|---|---|---|
| insn_add_ch0 | 24 | inconclusive: timeout | timeout |
| insn_lw_ch0 | 24 | inconclusive: timeout | timeout |
| insn_sw_ch0 | 24 | inconclusive: timeout | timeout |
| cover | 24 | inconclusive: timeout | not applicable |

A second finite trial used depth 10 with the same eight-second limit:

| Check | Depth | Result | Instruction activation |
|---|---|---|---|
| insn_add_ch0 | 10 | inconclusive: timeout | timeout |
| insn_lw_ch0 | 10 | inconclusive: missing or unreachable evidence | inconclusive |
| insn_sw_ch0 | 10 | inconclusive: missing or unreachable evidence | inconclusive |
| cover | 10 | retirement cover reached | not applicable |

The cover result establishes retirement reachability only. It is not an
instruction safety proof. The unselected ISA inventory, machine-state and
adapter-conformance rows remain gaps. Three selected instructions do not
cover RV32IM.

### SoC verification table

| Consumer | Generated | Ran | Result |
|---|---|---|---|
| protocol | yes | no | inconclusive |
| registers | no | no | inconclusive |
| vip | yes | no | inconclusive |
| uvm | no | no | inconclusive |
| connectivity | no | no | inconclusive |
| decode | yes | no | inconclusive |
| cdc_rdc | no | no | inconclusive |

The separate native CPU smoke and hello runs do not fill these consumer rows.
The hello test observed stores to a RAM mailbox through exported RVFI and
checked all 80 retirements with Spike. It did not exercise a UART. The default
map has RAM only. Peripheral and crossing qualification remain out of scope.
The composer now runs the project CPU. Automatic consumer binding and closure
are still incomplete.

### Retained evidence and limits

Raw receipts remain under `$RUN_ROOT`, the original clean-room scratch root.
The report cites these small records and logs:

- `second-mcp-init.log`, `second-mcp-plan.log`: real stdio calls.
- `core/rvw/out/sec-pair-second/report.json`: two native paired runs.
- `core/rvw/out/sec-flow-second/timeout.json`: precise flow preparation cap.
- `core/rvw/out/sec-flow-conservative/timeout.json`: conservative flow preparation cap.
- `core/rvw/out/formal-isa-second/result.json`: per-check depth-24 results.
- `core/rvw/out/formal-isa-depth10/result.json`: finite depth-10 trial.
- `core/rvw/out/uvm-mapped-fourth-run/results.json` and `run.log`: live pyuvm pass.
- `core/rvw/out/soc-final-run-images/results.json`: composed CPU smoke pass.
- `core/rvw/out/soc-hello-run/results.json` and `run.log`: mailbox output and 80 matches.
- `core/rvw/out/soc-verify-second/result.json`: seven unresolved consumer rows.
- `core/rvw/out/probe-third/result.json`, `probe-events.jsonl` and `konata.log`: final-cycle capture.

Both the precise and conservative flow builds timed out at 115 seconds.
Their owned caches were removed. No security-flow pass was
earned. The short proof budget did not earn any depth-24 instruction pass.
No BOOM run, full Python suite, long proof, CI wait or physical test was run.
The report does not claim that all four native capability gaps are closed:
flow completion and SoC consumer automation remain work.

Second-pass validation before the implementation pushes: final fast sets had
2,954, 2,963, 2,964, 2,969, 2,971 and 2,977 passes respectively. Each had one
skip. The first set retained the then-existing docs-site failure; later sets
passed. Final targeted follow-up selection: 52 passes. Guide and release
selection: 48 passes. The external terminal-probe native regression passed
once in 8.40 seconds. MCP discovery had no skipped modules. No rebase conflict
occurred, so union-rebase.sh was not needed.

Owned cocotb and SoC build directories were removed after validation. Small
logs, JSON, project sources and the cited probe stream remain.
