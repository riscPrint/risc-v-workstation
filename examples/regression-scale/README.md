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
