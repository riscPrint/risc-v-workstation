
## Required probe declarations

`rvw probes check` / MCP `probes_check` return `rvw.probes-check/1` with required
kind or kind/name entries and `missing_probes`. CLI exit 3 means inconclusive;
exit 0 means all requested declarations are present. Neither establishes
activation or semantic correctness. Default kinds are stage, retire, flush, stall.

## Stream validation

`rvw probes check --events E --validate [--c2 TRACE]` (MCP `probes_check` with `validate` or
`c2`) adds `stream`: `{status: clean|violations|inconclusive, probes, events, c2, findings}`.
`--c2` implies `--validate`. Without `--require`, validation checks no presence. Each finding
has `probe` (`kind/name`, or `stream`), `check` (`format`, `width`, `end`, `counter`, `id`,
`walk`, `c2`), `severity` (`error` or `warning`), `message` and `first_cycle` when known.
Checks: the stream reads under the contract; each value fits its field width; the end record
cycle is not before the last event and its per-probe counts equal the rows; every counter has
a total that fits its active cycles (a 1-bit counter equals them) and the cycle count; retire
and flush IDs were staged, close once, and are not staged again; each walker's responses end
in a result, and a successful result has responses. With C2: branch, interrupt, data bus and
CSR probes pass their `rvw probes convert` checks, and retire events equal C2 retirements.
The top-level `status` is `violations` when any error exists (CLI exit 1); a missing end
record gives `inconclusive` (exit 3). `clean` is not a proof of probe wiring.
