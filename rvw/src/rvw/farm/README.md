# Native regression farm

This increment supplies `rvw farm run`, `farm_run` over MCP, and
`rvw farm dashboard`. It uses native SSH, Python and the installed core adapter.
It does not choose a container policy. #59 remains an owner decision.

## Run

Install the same workstation and native tool builds on each worker. Configure
SSH login keys and trusted host keys. Obtain the local adapter's complete
`rvw.adapter-capture/2` identity document. Its result claims must include the
native build identity and a clean harness. Supply the identity command as an
argument array. Each worker must return the exact same identity document.
Different paths or tool identities can therefore refuse execution.

Write a JSON host array:

```json
[{"name":"worker-a","address":"host-a","python":"/opt/rvw/bin/python"},
 {"name":"worker-b","address":"host-b","python":"/opt/rvw/bin/python"}]
```

A host can set `ssh_options` to an array of native SSH options.
Prepare a C1 run-many JSONL manifest with explicit config and seed values.
The ELF is transferred by value. Other declared stimulus inputs must already
exist on the workers with the identity the adapter records.

```sh
rvw farm run --hosts hosts.json --manifest manifest.jsonl \
  --adapter '["/path/run.sh"]' \
  --identity-command '["/path/run.sh","identity","--config","small"]' \
  --identity identity.json --out /tmp/campaign --jobs 2 --timeout 600
rvw farm dashboard --root "$HOME/.cache/rvw/results" --out /tmp/dashboard.html
```

The output directory must be new. Rows get stable campaign-local IDs. The report
retains every expected cell, its options, ELF hash, shard results and missing IDs.
It preserves returned shard artifacts and checks their hashes. Each C1 result
must match its ELF hash, config, seed and all identity claims. A lost host,
identity mismatch, aborted shard or missing result makes the campaign
inconclusive (exit 3). A complete campaign can contain DUT failures. Exit 0 means
collection is complete. It does not mean pass or gate accept.

Use `rvw farm cancel --out /tmp/campaign` or MCP `farm_cancel` with `out` to
cancel a campaign. Each shard has a random control token. A separate SSH request
signals its worker. The worker unwinds `run_group`, stops all owned process
groups, and stores an acknowledgement on the host. The cancel endpoint uses
`ps` on the host to confirm that those groups have no live members. Zombies do
not count as live members. A lost host or missing acknowledgement is inconclusive.
`control.json` and `cancellation.json` retain the requests and replies. Keep the
campaign directory until cancellation finishes. This endpoint also works from
a later command after the dispatch process stops.

A host can set `resources`, for example:

```json
{"cpu": 2, "memory_bytes": 4294967296, "locks": ["native-build"]}
```

CPU slots must cover `--jobs`. Workers reserve these values under one host file
lock before they run the identity command or adapter. All aliases on the same
OS share capacity. Set `~/.config/rvw/farm-capacity.json` on each host to an object
with `cpu` and `memory_bytes`. Defaults reserve at most logical CPU count minus
one (minimum one), and half physical memory. Omitted memory means zero requested
bytes. Omitted locks means no named lock. A request waits up to the shard timeout
for capacity. The reply records reserved values and `queued_s`. Each request owns
its reservation. Normal completion, timeout and handled cancel release it.
These are cooperative reservations. They do not cap actual RSS or CPU use.
Adapters and unrelated processes can exceed them. Dead worker records require
owner cleanup after process groups are checked. No capacity is reclaimed blindly.

The dashboard reads C3, C4 and history. Missing evidence is inconclusive. It
shows per-status counts and plots recorded C3 `ipc` and `coverage` metrics by
core, suite and config. It also plots pass rate (conclusive passes divided by
all recorded tests) and run time (sum of all test `wall_s` values). Missing wall
times prevent a run-time sample. Charts and tables use oldest-first history and
retain gaps. Missing samples are not zero. It does not merge bins or
establish coverage compatibility or verification closure.

## Decisions and limits

- Workers own temporary directories and bounded process groups. Normal completion
  removes temporary data. SIGTERM and SIGHUP unwind group cleanup. SSH loss can
  leave the worker running until its declared timeout. Use the separate cancel
  endpoint to request acknowledged cleanup. Crash recovery remains open. SIGKILL
  can leave temporary data, control records and capacity reservations.
- Every run checks tool identity. This is a C1 execution interface, separate from
  `regress gate`. C8 cache admission and gate verdicts stay in the existing runner.
  Farm artifacts are not automatically imported as accepted C3 generations.
- The protocol buffers JSON and base64 artifacts in memory. Large waveform
  streaming, automatic discovery and campaign-scale performance work remain open.
- Requirements closure, retries, failure review, coverage-plan revisions, external
  review exports and licensed-tool scheduling remain open under #25.
- Test native SSH with two localhost entries. Set `RVW_TEST_SSH_OPTIONS` to a JSON
  option array for a test server. Run `pytest rvw/tests/test_native_farm.py`.
  These are protocol fixtures. They are not RTL verification results.

Collection checks explicitly requested `max_cycles` and `mem_latency` in each C1 result.
Missing or different values make collection inconclusive.

### Disk and project reservations

Host capacity also accepts `disk_bytes`, `jobs`, and `projects`.
`projects` maps project names to limits for `cpu`, `memory_bytes`, `disk_bytes`
and `jobs`. Missing project limits use the host limit. When this map is nonempty,
every request must name a configured `project`. Each project's simultaneous
requests share its limits, even through different host aliases.

Request `resources` can set the same four quantities and `project`. Disk and
memory default to zero; CPU and jobs default to one. Old host files default
disk capacity to half the free bytes and jobs to CPU capacity. The scheduler
also checks current free disk before admission. Reports include effective
`limits`, `queued_s`, `held_s`, `released` and `outcome`. Handled cancellation
releases every quantity. Requests above a host or project limit are refused.
Capacity conflicts wait up to the request timeout.

These are declared simultaneous reservations, not measured RSS, disk writes,
CPU quotas or cumulative project usage. A caller that declares zero memory or
disk reserves none. Direct third-party subprocesses do not acquire these limits.
Crash recovery still needs owner cleanup. Money rates and measured build and
simulation categories remain open under #57.

The dashboard also plots recorded C3 `sim_khz` and
`sim_instructions_per_s` per core, suite and preset. Missing values stay absent.
The denominator includes adapter execution and artifact handling. It excludes
model setup. These plots do not establish equivalent results or speedups.
