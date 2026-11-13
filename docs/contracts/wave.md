# Waveforms contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Wave index (`rvw.wave-index/1`)

`rvw wave index INPUT -o SNAPSHOT.rvwi` publishes an explicit SQLite snapshot.
It does not change C1 artifacts. The `metadata` table has one JSON `value` row
with `schema`, captured input `sha256`, `size`, original `source` path, `records`
`tools` (captured converter paths and SHA-256 hashes), and `header` (lines,
timescale, vars). Each var keeps code, name, width, kind and
range. The `events` table stores `seq` (integer primary key, file order), `t`
(signed 64-bit time), `code`, and unmodified `raw` VCD value. Timestamp records
have null code and raw. Indexes cover `(t, seq)` and `(code, t, seq)`.

The source hash identifies the captured input bytes, including compression.
The index is a saved snapshot, not a cache lookup against a live source. Queries
open a read-only SQLite transaction without a full source scan or capture-copy.
Publishers must not edit an index in place. Querying a snapshot establishes no
new simulator result or verdict. Unknown values retain their VCD meaning.

Optional metadata fields (older indexes lack them): `source_stat` (`size` and
`mtime_ns` of the source when indexing started; the build fails if they change
before publication) and `reader` (`vcd` or `wellen`). The `wellen` reader reads
FST natively through pywellen; its `tools.pywellen.version` records the library.
It writes change rows with `seq` at or above 2^40 in signal order, then one
timestamp row per distinct time with a smaller `seq`. Readers order by
`(t, seq)`; the order of different signals at one time is not significant for FST.

The cached form (`--indexed`, MCP `indexed`) keeps one index per absolute source
path under `RVW_WAVE_INDEX_DIR` (default `~/.cache/rvw/wave-index`). An entry
whose `source_stat` differs from the source is stale and is rebuilt before the
query. `rvw wave verify INDEX [--source WAVE]` compares full SHA-256 and returns
`fresh` true only on an exact match (exit 1 when stale).

## Failure-cause report

`rvw wave why-run` and MCP `wave_why_run` return `rvw.failure-cause/1`.
`cosim` is the strict Spike result. `cycle`, `time` and `clock` identify the
retirement in the selected wave. `chains` has one entry per bound mismatching
field. Each entry includes a navigation record, the method and accuracy.
`dynamic.graph` retains the SpinalTrace engine accuracy fields.
`driver_walk` is the existing active-driver report with control reads enabled.
The fallback is inferred, including when assignment conditions select a driver.
`status=inconclusive` means a required comparison, replay or wave mapping is
missing. `status=explained` means candidate chains exist, not a proven cause.
A replay must match order, cycle, actual retirement and differences before its
wave is used. It starts from reset. The wave window starts at most `window`
cycles before the mismatch and ends just after its sampling edge.
The binding, database and waveform association remains unverified.
