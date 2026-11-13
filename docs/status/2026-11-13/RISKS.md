# Risks and evidence limits

This is a document audit. The source ledger preserves each PR body. No code, test, build, simulation or proof ran for this audit. Evidence labels in ISSUES.md identify the strongest reported slice. They do not establish that every acceptance point passed.

## Highest risks

1. Broad closure from narrow reference tests. Debug issues #127, #133, #153 and #156 closed through #455, which explicitly has no core RTL target. #161 has Spike/OpenOCD evidence, not a real Debug Module endpoint. The owner must compare each issue with its required target. Do not treat reference behavior as RTL qualification.
2. Broad CSR closure. #85 closed today, but #861 binds one scratch word and leaves aliases, lower modes, WARL and autonomous updates open. #840 retains eleven fetch-contract findings. #87 also needs a field-by-field acceptance check against the captured machine CSR slice.
3. UVM scope. #296 closed today. #618 leaves CPU/SoC acceptance and advanced SV features open. #853 records native protocol failures and external-model stubs. The word UVM does not establish complete SV support or complete CPU verification.
4. Unqualified formal answers. #802 keeps conditional native passes inconclusive. #810 reports timeouts, abstract failures and reconstruction errors. #842 cannot solve its malformed export. Do not count these as core proofs.
5. Source and capture mismatch. #851 uses privately copied cached Vexii dependencies. It explicitly does not qualify a clean source build. #865 has model build and Spike evidence but no supervisor RTL program pass. Match runtime identity to the exact source and configuration before reuse.
6. Fresh-core transfer is bounded. #844 documents real smoke and four selected ISA tests. It also reports an absent VIP command and security IFT X/Z handling limits. #820's tiny fixture has no CSR, interrupt or trap implementation. Neither result establishes full unseen-core acceptance.
7. Short performance samples. #849 separates CPU cost, wall time and JVM reuse. #862 leaves model accuracy inconclusive. None of these establishes a general RTL speed or commercial accuracy claim.

## Areas with shallow or missing execution

- Privilege, MMU and extension campaigns often ran on Spike or Python only. #821 explicitly did not run DUT/RTL. #860 did not run the actual input/clock adapter. #836 reports installed Spike refuses Ssstateen. Do not credit architectural DUT coverage from generated programs or fixtures.
- Architecture changes often use synthetic schedules and saved observations. #803 did not run held-out RTL accuracy or speed qualification. #813 did not run Spike wrong-path replay or RTL. #862 adds a real in-order slice but does not qualify the complete OoO model.
- Coverage closure has layered evidence. #468 did not run a native DUT event campaign or held-out event goals. #643 seals attempts. #686 replays sealed ELF inputs without new credit. #740 adds code-coverage goals. A candidate, dispatch or sealed report does not establish new closure.
- IDE views #845 through #870 report typecheck, build and unit tests. Their bodies state that live VS Code checks did not run. A saved-data view is not a checked interactive debug workflow.
- Agent benchmark #817 did not run LLM/API calls or native repair trials. #830's native attempts exhausted short limits without C1 results. Static fixture scoring is not evidence of successful agent repair.
- Installation #685 explicitly declares untested Linux recipes. Local tools and a version table do not establish a clean-host reproducible install.
- Device models and cacheless SMP are limited. #835 uses simulation RAM, atomic service and devices. It has no synthesized coherent fabric or cache. #814 runs FreeRTOS, not Linux or OpenSBI.

## Overlapping implementations to reconcile

| Overlap | Source paths and PRs | Required owner check |
|---|---|---|
| Checkpoint and replay paths | Native snapshot envelopes #425; harness/writer state #438; architectural injection #459; reverse step #465; live Vex restore #544/#580; hierarchical replay state #776; device checkpoint #814. Paths under RiscvSim, rvw sim and formal replay. | Distinguish architectural state, native model state, writer order, memory, device state and replay stimulus. Require equivalent identity and suffix checks for each supported path. |
| CSR models | Formal CSR artifacts #384, shared catalog #458/#671/#695, UVM RAL #469/#605, SoC register exports #731 and live CSR capture #721. Paths under SpinalChecks/csr, rvw csr, Uvm and rvw soc. | Use the same alias, WARL, privilege and side-effect semantics. Check independent observation sources. One shared model cannot be both DUT evidence and its only oracle. |
| Coverage closure loops | Integer solver #408/#431, sequence actions #452, RTL-event guidance #468, UVM constrained stimulus #618, plan rollup #567, code goals #740 and evidence indexing #604. | Prevent duplicate credit. Preserve denominator, identity, complete-run and independent-observation requirements. Distinguish planning from execution. |
| Security paths | Formal security #416/#513/#564/#757/#842, dynamic rvw sec #696/#700/#715/#717/#720 and fault campaigns #556/#689. | Keep model taint, two-copy proof, timing measurements and fault detection as separate claims. None implies full physical or whole-core security. |
| Memory references | Serialized observations #385, axiomatic graph search #477, coherence model #554, generic concurrent execution #741 and cacheless real-core SMP #835. | Do not use serialized success as weak-memory or coherent-cache acceptance. Require physical dependencies and explicit unsupported-event refusals. |
| Navigation interfaces | rvw query semantic navigation #793, LSP #798, saved VS Code navigation #845 and HDL diagrams #688. | Compare identity, source locations, ambiguity and generated-source handling. Avoid separate stale database copies. |
| Evidence and planning | rvw evidence #604, rvw plan #567, farm workflow #615 and agent guide #649. | Establish which layer owns verdicts. Indexing a report must not strengthen its producer verdict. |

These are functional overlaps. This audit does not claim that duplicated code is identical or defective.

## Contract and document inconsistencies

- ROADMAP.md retains claims that full SV, Chisel and VHDL query support is open. Today's slang, GHDL and FIRRTL paths add supported subsets. Replace that broad wording with the actual front-end limits. #832 and #839 show why lowered connectivity needs careful interpretation.
- The commercial comparison says there are 64 built-in MCP tools. Today adds profiles, a catalog and envelopes in #846/#857/#867. Use a generated inventory for exact counts. This audit did not execute discovery.
- ROADMAP.md says farm service, crash recovery and closure planning are pending. #570/#615/#641 add slices of those functions. Their presence does not establish cluster-scale acceptance. #680 adds explicit completion-evidence requirements.
- Command-reference policy changed during the push. The worker brief deferred edits and its test. #667, #785 and #786 regenerate the reference. Generation time and current parser inventory must match before the owner claims complete documentation.
- Contract placement changed in #610/#645. The worker brief records that union merges broke formal MCP discovery twice. A successful import alone is insufficient. This audit did not execute parser or MCP checks. #828 adds static parse coverage; it does not replace native discovery.
- PR #381 freezes acceptance sources and separates organisation work from tool acceptance. Today's implementation status cannot replace its cell rules or remove mandatory predecessor evidence. The proposals preserve this separation.
- Some fast runs report unrelated documentation or personal-path failures. They are failures, not clean suite results. Later fixes may supersede them. Read the retained per-PR counts rather than combining pass counts from different heads.

## Audit limits and refresh rule

The midnight census uses current issue bodies and closure/reopen event times. It does not recover historical body edits. The collection includes PR body references that can be context links. A missing reference can hide related work. Evidence labels use a conservative source review and must be checked before closure. No issue is suggested closed merely because GitHub closed it.

Every refresh must retain this evidence boundary. Collect new PRs, update the census and source ledger, then review superseded limits. Keep raw JSON outside the repository. Make a small documentation PR. Do not edit issues, ROADMAP.md or TODO.md.
