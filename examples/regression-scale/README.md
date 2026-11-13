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
