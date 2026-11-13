# BOOM probe bindings

These bindings observe the private core clone. They do not change core RTL.
Enable them with `--probes`. Use `small` for the bounded native checks.

| Probe | Source and unit | Limit |
|---|---|---|
| `fetch_prediction_*` | Fetch packet dequeue, one event per valid slot | The PC is the packet PC. The slot is a halfword position. This is not a retirement ID. |
| `execute_branch_*` | Valid branch-unit resolution | Events can include speculative instructions. |
| `conditional_commit_*` | Architectural branch commit, retained outcome, target and enqueue prediction | The ROB index only addresses retained state. It is not an external instruction ID. |
| `mispredict_redirect` | Frontend redirect request | Separate the flush and mispredict fields. A redirect is not always a branch correction. |
| `branch_mispredict` | Branch correction pulse | Includes speculative correction work. It does not equal committed-path model misses. |
| `commits`, `architectural_commits`, `predicated_off_commits` | ROB commit slots per cycle | Architectural and predicated-off counts must sum to total commits. C1 excludes trap records. |
| `rob_occupancy` | Sum of all ROB slot validity bits | The binding checks the expected row count. The native checks cover only small. |
| `rob_head_occupancy` | Valid slots in the ROB head row | This is not full ROB occupancy. |
| `rename_*_free`, `rename_*_allocated` | Physical free-list levels | These are levels, not allocation event counts. |
| `rename_occupancy` | Valid dispatch slots | This is not the number of allocated physical registers. |
| `issue_*_occupancy` | Valid collapsing issue-queue slots | Banked and matrix queues need other bindings. |
| `dispatch`, `rename_*`, `dispatch_*` stalls | Direct ROB-full, rename-stall and dispatch-stall signals | Each total counts active cycles. Causes can overlap. No instruction ID is inferred. |
| D-cache `lookup_*` | Stage-2 valid lookup address and hit signal | A lookup can also nack. A lookup miss does not prove a memory refill. |
| `dcache_*` nack stall | Stage-2 valid and nack | Counts active cycles. |
| I-TLB and D-TLB miss | Valid lookup with miss | A stalled request can produce repeated samples. Zero events do not exercise the binding. |
| I-cache response | Valid response and physical PC | This does not classify cache misses. |
| PTW request and response | Accepted memory request and valid response | These are walk memory transfers, not complete TLB fills. |

The counter converter sums each cycle's value. Occupancy totals therefore use
slot-cycles. Divide by the sampled cycle count to get mean occupancy. Keep the
sample window explicit. Do not map an occupancy integral to a stall counter.

Use `conditional_commit_0` with the branch-event converter on small. The
converter checks event count, PC and branch outcome against C2. It refuses a
missing event. Fetch predictions and execution events use separate streams.

The ROB repairs `uop.taken` after a mispredict (`rob.scala:437,464`).
The binding saves the prediction at enqueue. It does not read the repaired
commit value as a prediction. The capture regression requires a direction
difference in the branch-heavy smoke programs. The earlier capture fails
that regression.
