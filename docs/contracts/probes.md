
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

## Reused instruction IDs and ROB-tail flushes

A stage probe can set metadata `first: "true"`. If any stage has this flag,
only a first-stage event starts an instruction in the Kanata converter.
Late events for an ID that is not live count as `orphan_events`. Multiple
lanes can share a stage name through `Probe.stageAt` with distinct probe names.

A flush probe can set `range: "younger"` and provide `id` and `inclusive`.
It closes all live instructions that entered after the last instance of the
anchor ID. It also closes the anchor when `inclusive` is nonzero. Entry order,
not the numeric ROB index, defines age. An unknown anchor increments
`unanchored_flushes`. A reused live ID that reenters after another stage closes
the old instance as flushed and increments `stale_closed`. These counts expose
incomplete bindings. They are not proofs of pipeline tracking correctness.

The end record can add `first_cycle` and `last_cycle`. They give the inclusive
bounds of actual sampling, including idle cycles without event rows. Both must
be present together. The Kanata converter preserves these bounds. Older streams
without them keep their observed event window; `cycles` alone does not define
a cycle origin. RiscvSim supplies both bounds after at least one sample.

## Physical cache lookups and retired attribution

Cache metadata can declare `semantics=retired-refill-attribution`. Such an
`access` attributes a refill to a retired instruction. It is not a physical
tag lookup. A buffered instruction can retire after its line is invalidated.
Producers that use this attribution also emit physical `lookup` events with
actual tag-hit values. The cache checker checks residency on those events.
It counts retired attribution separately. Attribution without physical lookup
events is inconclusive. False hits on physical lookups remain violations.
Whole-cache flush events occur when invalidation completes.

Performance recovery spans are producer declarations. The example spans start
at a redirect and end at decode occupancy or the next commit. They are
`inferred`. Cache refill activity and recovery can overlap. Their sum is not
a total of lost CPU cycles. The VexiiRiscv stage view covers its commit stage
only. A C1/trace count mismatch remains visible in the performance report.

Instruction caches can restart after one returned word. `refill_beat` events
carry the physical byte address and returned bytes. The cache checker checks
each beat against the independent memory image. Before full-line completion,
a lookup hit requires every requested byte to be present in the beat inventory.
Its data must match memory. A hit on another word remains a violation. Fill,
eviction and flush events clear the corresponding partial-byte inventory.

## Measured causes and producer dependencies

The `dependency` probe has fields `id` and `producer`. Both name instruction
IDs from the stage probes. `Probe.dependency` declares this event. Kanata
conversion writes a W edge and retains producers that already retired.
Unknown consumers or producers are errors. An edge records data flow. It
cannot establish that the consumer stalled or that the edge caused a stall.
Explicit `stall` samples remain the only source of measured stall causes.

`rvw probes check --consumer perf-causal` names the required stage ID,
retirement ID, stall sample and dependency ID/producer bindings. MCP accepts
the same `consumer` field. This checks declarations. It does not prove wiring
or activation. Convert the captured events to Kanata and use `rvw perf` for
measured cause counts and the remaining unknown zero-retirement intervals.
