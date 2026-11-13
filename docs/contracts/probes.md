
## Required probe declarations

`rvw probes check` / MCP `probes_check` return `rvw.probes-check/1` with required
kind or kind/name entries and `missing_probes`. CLI exit 3 means inconclusive;
exit 0 means all requested declarations are present. Neither establishes
activation or semantic correctness. Default kinds are stage, retire, flush, stall.
