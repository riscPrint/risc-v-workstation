
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

## Cache event checks

`rvw probes convert EVENTS --to cache-check --c2 TRACE --elf ELF --out OUT`
checks fill and writeback bytes against ELF bytes and retired C2 stores.
`--geometry CACHE=SETSxWAYS` enables set capacity checks. A hit requires a
resident line. A fill requires space or a prior eviction. Without an eviction
probe, the checker counts implied evictions. For multiple ways it marks victim
identity as unknown and counts unchecked hits. A flush clears resident lines.
The report schema is `rvw.probe-cache-check/1`. Status is `consistent`,
`mismatch` or `inconclusive`. Consistency applies only to the checked rules.

`rvw csim compare-rtl STUDY --cache dcache --trace TRACE --events EVENTS`
compares each retired memory access with an RTL cache access. `compare-cache`
is an alias with the same cache options. MCP exposes `csim_compare_cache` and
`csim_compare_rtl` with `cache`. `--level l1i` selects instruction accesses.
The report schema is `rvw.csim-cache-compare/1`. It gives per-access differences,
RTL and model miss rates, signed miss-rate error, and per-PC counts. Missing
identity, incomplete streams, unequal counts, address or write-direction
differences give `inconclusive`. An unsampled tail remains inconclusive.
`compared` means the aligned accesses were compared. It is not a correctness
verdict. `--trace-out` writes the aligned RTL access stream for further studies.

Cache study levels accept `write_allocate` and `write_back` booleans.
Both false select write-through with no allocation on store misses.
