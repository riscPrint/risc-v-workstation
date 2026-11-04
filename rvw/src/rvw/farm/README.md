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

The dashboard reads C3, C4 and history. Missing evidence is inconclusive. It
shows per-status counts and plots recorded C3 `ipc` and `coverage` metrics by
core, suite and config. Missing samples are not zero. It does not merge bins or
establish coverage compatibility or verification closure.

## Decisions and limits

- Workers own temporary directories and bounded process groups. Normal completion
  removes temporary data. SIGTERM and SIGHUP unwind group cleanup. SSH loss can
  leave the worker running until its declared timeout. Immediate remote cancel
  acknowledgement and crash recovery remain open. SIGKILL can leave temporary data.
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
