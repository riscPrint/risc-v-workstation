# Security runs on NaxRiscv

Project data for `rvw sec` (see `rvw/src/rvw/sec/README.md`). NaxRiscv speculates
(out of order, branch prediction, write-back caches), so this is the first core
where the speculative self-tests can find a transient leak.

The native sec harness cannot drive NaxRiscv's refill buses or read a C2 trace
from it. `run.json` (`rvw.sec-run/1`) selects the C1-run case adapter
(`python -m rvw.sec.run_adapter`) instead: it calls this project's `rvw/run.sh run
--rvfi-trace --probes` and reads the C2 trace and the probe stream.

```sh
export NAXRISCV=/path/to/NaxRiscv RVW_NAX_LOCK=nax-private RVW_NAX_SBT_LOCK=sbt-private
rvw sec contract --manifest rvw/sec/ct.json --out out/ct
rvw sec spec-suite --binding rvw/sec/run.json --template rvw/sec/spec.S --out out/spec
rvw sec contract --manifest rvw/sec/spec-v1-control.json --out out/v1-control
rvw sec campaign --manifest rvw/sec/campaign.json --out out/campaign
```

- `ct.json`: the constant-time divide and multiply program of the other examples.
- `spec.S`: the spec-suite template (`sec_probe`, `sec_slot`, `sec_public`).
- `spec-v1-control.json`: the v1 gadget with the wrong-path load replaced by `nop`.
- `campaign.json`, `campaign.S`: the campaign with all channels this run gives
  (`cycles`, `retire_cycles`, `branch_events`, `cache_events`, `tlb_events`,
  `probe_events`, `probe_counters`). The NaxRiscv probes have no cache access or
  TLB events, so those lists stay empty; cache effects show in timing and the
  refill counters. Bus channels need the native harness.

Each case is a full C1 run (about one to two minutes on a loaded host), so
reductions and campaigns are slow. Results and findings: `../../FINDINGS.md`.
