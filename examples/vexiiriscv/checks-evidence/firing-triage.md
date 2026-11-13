# Wider ISA firing triage

The [record](firing-triage.json) lists all programs behind the 139 events.
It includes one wave window per firing check, the core revision and ELF hashes.

| Check | Events | Decision | Source |
|---|---:|---|---|
| PC payload stability | 103 | Tool false positive: the binding omitted current redirects. | `PcPlugin.scala:67-100` |
| Divider response valid hold | 36 | Tool false positive: the binding omitted the previous flush. | `DivRadix2.scala:187-190`, `DivPlugin.scala:116-117` |

The PC window uses `rv32ui-p-add`. At 539 ps the old sequential offer is
stalled. At 549 ps `forcedSpawn` selects the redirect. The stream still has
valid set. The previous hold-only binding did not cancel the old offer.

The divider window uses `rv32um-p-div`. At 3659 ps response valid is set and
ready is clear. The flush edge clears `done`. At 3679 ps valid is clear.
The consumer uses flush to consume this response. It keeps ready clear.
The correct cancellation sample is the previous cycle.

Reproduce with `rvwvexii.CsrChecksRuntime`, the pinned private core,
`RVW_CHECKS_ISA=1` and `RVW_CHECKS_WAVE=1`. Pass the CSR model, an empty output
directory, `none`, and the add and div ELFs. The pre-fix revision fails both
checks. The fixed bindings retain checks outside the reviewed conditions.
The core sources do not change.

The fixed runtime then ran all 49 aligned ISA programs and both CSR programs.
All 51 software and check gates pass. All 25 checks remain inserted. No check
fires. This result does not establish full activation or whole-core proof.
