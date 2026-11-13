# Native regression management example

Use the workstation Python environment. Set `RVW_HOME` to the workstation
checkout. Set the example's source environment variable to a private core copy.
Set `RVW_VEX_LOCK=vex-priv` and `RVW_SBT_LOCK=sbt-priv`. Set `RISCVSIM_WORK`
to a private model directory. Source the native tool environment.

Build the example's ISA programs with its `rvw/build-tests.sh`. Prepare a JSONL
manifest with absolute `elf` paths, `config`, `seed`, `max_cycles`,
`mem_latency` and `rvfi_trace: true`. An optional `id` names the test in C3.
This example removes `id` before it calls the C1 adapter.

```sh
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" submit.py \
  --manifest jobs.jsonl --adapter '["/absolute/example/rvw/run.sh"]' \
  --root /tmp/native-queue --shards 2
rvw farm queue --root /tmp/native-queue --operation work
rvw farm queue --root /tmp/native-queue --operation work
rvw farm live --root /tmp/native-queue --owner local
```

Each `work` call executes one shard. Start no more than three workers on the
shared host. A single private core lock serializes model builds and runs.
A complete queue job means collection complete. Read C3 for DUT outcomes.
Results remain under `QUEUE/JOB/attempt-N/`. Keep every attempt.

Run `controls.py` with the same `--manifest`, `--adapter` and a new `--root`
to test controller death, checked recovery, retry and cancellation. It kills
only the worker it starts. It requires the recovered process group to stop.
It records `controls.json`. The retry must collect complete native evidence.
Cancellation must finish with no live members in the captured process group.

The initial cold-build attempts exposed an invalid management `id` in the C1
manifest. The adapter refused the request. Those attempts collected no tests.
The wrapper now strips that field. The negative attempts remain in local logs.

C4 acceptance, reference comparison and design coverage are separate checks.
This example does not infer any of them from C1 status or queue completion.

The recorded local run collected all 49 VexRiscv ISA tests as C1 and C3.
Both serial shards used one native session each and the same generated RTL.
The measured shard times were 65.80 and 130.71 seconds. Their sum includes
adapter startup and private-lock wait while a control ran. The resulting rate
was 0.249 tests per second. This is a shared-host observation. It excludes the
earlier invalid-manifest attempts. See `local-results.json` for the source
revision and the startup crash/retry and cancellation controls. The harness
was dirty during this first run. Gate acceptance and new Spike comparison
were NOT RUN. Native-session crash controls are recorded separately when run.

## Recorded dual-core dashboard

`history.py --out HISTORY QUEUE...` copies terminal job records and their
artifacts into one local history. It keeps source C3 hashes and original
attempt locations in import metadata. It does not create executions.
`--skip-active` lists and excludes active jobs. Export with:

```sh
rvw farm live --root HISTORY --owner native --out recorded.html
```

[The recorded example](../../docs/examples/regression-dashboard.html) has seven
native queue records and 221 test observations. It includes two VexiiRiscv ISA
runs, two VexRiscv ISA shards, a 25-test retry, a cancelled job and a planted
VexRiscv fault run. Both VexiiRiscv runs passed all 49 tests. The fault changes
XOR to OR in a private committed core copy. It produced 47 passes and two
failures. The initial cluster has one C5 bundle. The authenticated API returned
401 without a token and no runs for a different owner. Bundle drill-down read
the recorded C5 summary. Exported paths use `$CHECKOUT` or `~`.

The fault run exposed an incorrect collection rule for adapter exit code 1.
The runner now accepts that code only when complete conclusive C1 evidence
contains a DUT failure. The original error record remains in the example.
The live reader also skips C5-owned storage when it scans C3 history.

Fresh strict reference checks on VexRiscv found an unknown `mscratch` reset
value at the first instruction. Those mismatch records remain local. The
existing reset-only synchronization policy allowed clean add/xor/xori traces
to match and found wrong GPR data in both planted-fault traces. Each VexRiscv
check used one CSR reset synchronization. The VexiiRiscv sample checks matched
with zero synchronizations. These samples do not establish full-suite strict
reference matches. C4 gate acceptance was NOT RUN for this history.

The [single-run export](../../docs/examples/regression-dashboard-run.html)
contains the planted-fault run alone, including its C5 summary. Use
`history.py --job JOB_ID --out ONE_RUN QUEUE` before export to select one job.

The stronger controls also passed after a real native C1 result appeared.
The controller was killed with SIGKILL. Recovery stopped the native group and
retained the infrastructure attempt. The retry collected 25 tests. A separate
cancellation stopped its native group and finished as `cancelled`. Both native
JVM group checks found no live members. `dashboard-results.json` records the
control report hash and outcomes.

## Native failure triage

`triage-results.json` compares 49 good cells with the 49-cell private fault run.
The diff reports two new failures. Captured reset-only Spike comparisons split
the failures into two PC/instruction signatures. XORI first differs at
`0x80000198` (`0xf0f6c713`). XOR first differs at `0x800001a0` (`0xc5c733`).
Each cluster has a C5 bundle. Both comparisons record one unknown-CSR reset
synchronization. No masks hide the GPR differences. The record includes the
exact good-to-bad range and `rvw bisect` argument arrays. Native bisection was attempted. Input capture refused the tracked
`src/test/resources/VexRiscvRegressionData` gitlink before simulation. No
endpoint or first-bad result was earned. The capture check was kept intact.
These XOR failures did not exercise a trap-cause signature.

## Native impact selection

`selection-results.json` records a separate private control fixture. Its base
commit enables line comments and removes the unused test-data gitlink. No
capture check changes. The baseline supplied 49 passing native runs, 1,585
Verilator coverage points and a 1,033-signal design database. `farm observe`
read captured FST waves. Its corrected mapping retains all aliases of each
wave code. The catalogue and two-second plan were frozen before candidate
execution. A later alias fix replay kept the same 49 selected test IDs.

The candidate changes the example's split-add/sub option and plants the XOR
fault. Coverage selection cannot map either edited source line. It therefore
requires all 49 tests. The farm plan preserves that requirement and reports
its 61.89-second estimate as over budget. The separate full and selected runs
both report 47 passes and two failures. This caught the planted fault through
full-suite fallback. It does not qualify test reduction.

The baseline point-coverage ranking chose eight tests. A separate native run
of those eight tests passed all eight and missed the fault. Point coverage is
not functional coverage. Do not use that ranking alone as a gate. No candidate
outcomes were used to form the frozen plan. Native test times include model
startup in the first test. The two-second value is an advisory selection
budget, not an enforced execution limit. C4 acceptance was NOT RUN here.

## Native budgets and unit costs

`budget-results.json` records real adapter executions on the committed private
fault fixture. A one-job run budget stopped the declared DUT-failure retry.
The original C1 failure remains recorded. A one-job agent budget allowed a
native add test to pass and blocked the next job before launch. A 0.2-second
run wall budget ended a native adapter launch with no C1 verdict. Cleanup made
its charged wall time 0.399 seconds. The private core lock was free afterward.

Three attempts used 145.751 wall seconds and 0.080973 declared core-hours.
At an illustrative rate of one caller unit per core-hour, the cost was
0.040486 units per conclusive C1 observation across one pass and one failure.
The charge includes the timed-out launch. CPU use is declared, not measured.
There are no C4 reports in this budget experiment. Its C4 unit cost is null.
Later committed gate runs supply that separate measure.

## Committed native gate cases

`gate-results.json` records clean committed core and harness revisions, every
input ELF hash, RTL/native-build hashes and C4 report hashes. Native execution
used a separate clean tooling clone. Good base and repeat runs each passed 49
ISA tests. A distinct revision keeps the split-adder edit and restores XOR. It passed
all 49 tests. The private fault revision passed 47 and failed two. Farm intake
checked every C1/C3 pair. The existing gate engine accepted both the repeat and the distinct passing revision and
rejected the fault revision for two new failures. Both compared 49 tests.
The existing `rvw regress gate` CLI also returned 0 for accept and 1 for reject,
with explicit separate verdict destinations.

The first native runs exposed model-build keys in C3 execution options. The
formatter now keeps those keys in `native_options`. Corrected cases were rerun
from native execution. The original records remain. Incomplete native source
identity marks C3 source incomplete and cannot earn gate accept. The gate's
requested-plan checks were preserved.

Queue attempts retain C4 values separately from transport completion. Across
all ten queue jobs, including the formatter debugging runs, charged wall
time was 479.759 seconds. At two declared cores and an illustrative rate of
one caller unit per core-hour, cost was 0.088844 units per recorded C4 report.
The separate manual CLI checks are outside that queue scope. This is a cost
per report, not per unique proof. Acceptance covers these 49 ISA self-checks.
It does not qualify the whole core, formal behavior or fresh Spike parity.

## Same native shard plan and Kubernetes Jobs

`k8s-results.json` records a fresh local persistent run using `farm plan` and
`LocalExecutor`. The two shards contain 25 and 24 ISA tests. All 49 passed.
The queue ran one simulation at a time and completed in 54.016 seconds.
Collection checked 49 C1 results and two C3 suites. The inputs, core revision,
harness revision, result hashes and times are retained in the report.

`k8s-example/` is that plan with explicit path relocation to `/work/results`,
`/work/core` and `/opt/rvw`. Its test IDs, ELF hashes, options and shard members
are unchanged. `render_k8s.py` performs this relocation from a local plan with
repeated `--replace OLD=NEW` arguments. It renders both Jobs and validates
them against a supplied official Kubernetes OpenAPI v2 file. The stored report
uses the v1.34.1 URL and records the schema hash. Removing `containers` caused
the expected validation failure. The example image is unbuilt.

A real cluster run still needs all of these steps:

1. Build and pin a Linux worker image by digest. Install matching native tools,
   dependencies, the committed SDK and committed core project. Test the C1
   adapter and its persistent server in that image. macOS build hashes cannot
   establish Linux identity. Replace the placeholder image in the plan.
2. Stage every hashed ELF and shard manifest on storage mounted at
   `/work/results`. Verify the recorded input hashes. The export does not carry
   ELF bytes. Use an RWX PVC, or another reviewed placement and storage policy
   that gives both pods their expected files. Provision the named PVC first.
3. Provide private writable build directories, dependency caches and lock
   namespaces for each worker. Set `RVW_HOME`, `RVW_PYTHON`, `VEXRISCV`,
   `RVW_VEX_LOCK` and `RVW_SBT_LOCK` for that layout. The explicit adapter array
   shows the intended paths. Pin JVM and Verilator worker counts in the image.
4. Select a real kubeconfig, context and namespace. Check RBAC, image pull
   access, node architecture, resource requests, limits, quotas and Job API
   support. Offline schema checks cannot establish these facts. Local queue
   cumulative budgets do not enforce Kubernetes quota or provider charges.
5. Submit the rendered plan through the Kubernetes executor. Save every Job
   ID. Check pod logs and Job completion. Collect with `--executor k8s --ids`
   and validate the returned C1/C3 evidence. Use native gate intake with clean
   source identities before requesting C4 accept.
6. Exercise foreground cancellation and process cleanup in the cluster.
   Keep `backoffLimit: 0`. Use new output roots for explicit retries. Measure
   cluster queue time, runtime, charges and throughput before claiming scale.

Cluster submission, admission, PVC binding, container builds, cancellation and
pod execution were NOT RUN. No cluster capacity or Linux parity is claimed.
