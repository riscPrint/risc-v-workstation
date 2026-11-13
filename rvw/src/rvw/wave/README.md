# rvw wave

Streaming queries on VCD and FST waveforms, for agents and scripts. Replaces BOOM's `tools/vcdq.py`
(`vcdq.py wave.vcd REGEX --from T --to T` is `rvw wave changes wave.vcd REGEX --from T --to T`).
Nothing is BOOM-specific.

```sh
rvw wave info    WAVE                          # timescale, #signals, first/last time, clock period
rvw wave list    WAVE [REGEX]                  # signal names and widths
rvw wave changes WAVE REGEX [--from T] [--to T] [--limit N] [--dec]  # N defaults to 10000; 0 = all
rvw wave sample  WAVE REGEX --at T|end [--dec] # value of each matching signal at T
rvw wave cut     WAVE --from T [--to T] [--signals REGEX] [--rebase] -o OUT.{vcd,vcd.gz,fst}
rvw wave find    WAVE EXPR [--from T] [--to T] [--limit N]   # first/last/all intervals where EXPR holds
rvw wave edges   WAVE REGEX [--from T] [--to T]               # changes, rising/falling, x/z per signal
rvw wave index   WAVE -o OUT.rvwi [--reader auto|vcd|wellen]  # build an indexed snapshot
rvw wave verify  OUT.rvwi [--source WAVE]                     # full SHA-256 check; exit 1 when stale
rvw wave why     WAVE SIGNAL --at T --db DESIGN.db [--depth N]  # active drivers behind a value
rvw wave seq     WAVE 'a ##1 b ##[1:3] c' [--clock RX]          # clocked sequence matches/failures
rvw wave txn     WAVE --valid V [--ready R] [--payload RX]      # Stream/Flow transfers and issues
rvw wave txn     WAVE --stream io.cmd --db DESIGN.db            # same, signals typed by the database
rvw wave diff    A B [--signals RX] [--offset N] [--map P=Q] [--on-clock] [--all]  # exit 1 on divergence
```

Every query command takes `--indexed`: it queries a cached index of the wave and builds
it on first use (see "Indexed snapshots").

All commands take `--json`: stdout is then one JSON document. Wave and argument errors return
`{"error": "message"}` with exit 2. Capture and JSON serialization errors leave stdout empty.
Errors also print a message on stderr.

- Signal names are dotted scope paths including the top scope (`TOP.BoomSimTop.tile.core.rob_1.rob_head`);
  `REGEX` is a Python regex searched anywhere in the name. A separate declared bit range (`[7:0]`) is not part of the name.
  Brackets within the reference token remain part of the name, including `a[0]` and `\a[0]`.
- Times are in the wave's units. `Nc` means cycle N: the period comes from `--period` or is detected
  from the first rising edges of the clock (`--clock`, default `clk`/`clock`).
- Values: scalars `0 1 x z`, vectors in hex (`0x1f`), or `b01x0` when some bits are unknown; `--dec`
  prints decimal.
- `changes` stops after `--limit` changes (default 10,000; `0` = no limit). `--json` prints
  `{"changes": [...], "truncated": true|false, "limit": N}`; the text output says on stderr when it
  was truncated. The `wave_changes` MCP tool returns the same object.
- `cut` refuses to write over its own input.
- `cut` writes a self-contained file: a `$dumpvars` block with every kept signal's value at the window
  start, then the changes up to `--to`. Combined with `--signals` this turns a multi-GB BOOM wave into
  something Surfer or an agent can open. FST input and output go through GTKWave's `fst2vcd`/`vcd2fst`
  (on `PATH`).

## Expression search

`find` evaluates an expression at the window start and after all changes at each time where
a referenced signal changes. It returns `first` (first time true), `last` (the last true
interval), `matches` (intervals `{start, end}`; `end` null means true through the window end),
`count`, `true_time`, `steps` and `unknown_steps`. Syntax:

- signal names: a dotted path, or a unique suffix (`valid`, `rob.head`); quote other names in
  backticks (`` `TOP.mem[3]` ``). An ambiguous or unknown name is an error.
- operators: `&& || !` (or `and or not`), `== != < <= > >=`, `+ - * // % & | ^ ~ << >>`,
  bit selects `sig[7:0]`, `sig[3]`, integer literals (`0x2a`).
- functions: `rose(s)`, `fell(s)`, `changed(s)`, `stable(s)` (against the previous evaluation
  point), `known(s)`.
- x/z bits make a value unknown; a bit select keeps known bits known. An unknown result is
  never a match and counts in `unknown_steps`.

`edges` counts value changes per signal (a repeated dump of the same value is not a change,
the first value is not a change), rising and falling edges for 1-bit signals, and transitions
to or from x/z under `unknown`. Both read only the referenced signals' rows from an index.

## Active drivers (`why`)

`why` joins the wave with a SpinalDB database (`--db` or `RVW_DESIGNDB`). For the signal it
reports the value at T, every database assignment with its `when`/`switch` chain, and which
one was active. A condition holds when its condition signal (`conds.signal_id`, for example
`when_Gcd_l19`) has a known value that selects it; `switch` cases compare literal keys.
The last full-width assignment whose chain holds wins; an undecided later assignment makes
the node `ambiguous`. A register is explained at its last value change: `set_at` is that
time and the drivers are evaluated just before it (`evaluated_at`). An asserted reset gives
`status: reset`. The walk follows `data` reads up to `--depth` levels and `--max-nodes`
signals. Node `status`: `active`, `held`, `reset`, `initial`, `ambiguous`, `no_driver`,
`no_active_driver`, `unresolved` (no wave signal) or `seen`. The wave is read through a
cached index. The result says `binding: unverified`: names are joined by wave path, and the
wave and database are the caller's choice. Partial-range assignments are listed but do not
combine bits.

## Clocked analyses (`seq`, `txn`) and `diff`

Clocked commands sample signals at each rising edge of `--clock` (the shallowest 1-bit match)
with the values just before the edge. `rose()`/`fell()` then compare with the last edge.

`seq` takes expressions joined by `##N` or `##[lo:hi]` cycle delays (`hi` may be `$`). Each
edge where the first expression holds starts a thread. A thread advances at the first edge in
its window where the next expression holds, fails when the window passes, and is `pending`
when the wave ends. The report lists matches, failures (with the failed step) and pending
starts. Unknown values never advance a thread.

`txn` reports Stream transfers (valid && ready) or Flow transfers (valid; no `--ready`) with
their payload and wait cycles, stall and idle edges, throughput and two protocol issues:
`payload_changed` (payload changed while valid && !ready) and `valid_dropped` (valid fell
before ready). `--stream PATH --db DB` takes valid, ready and payload from a Stream/Flow bundle
in the database. Edges with unknown valid or ready count as `unknown_edges`, not transfers.

`diff` pairs signals by name (`--map A_PREFIX=B_PREFIX` renames, `--offset` shifts B) and
compares values by meaning (x/z bits differ from known bits). Without `--on-clock` it compares
at the window start and at every time either wave changes; with it, at A's rising edges. It
stops at the first divergence (`--all` scans on and lists each signal's first divergence).
`status` is `match`, `diverged` or `no_points`; the CLI exits 1 unless `match`. The
alignment is by time only, not by retirement or transactions.

Python API (used by `rvw bundle`): `rvw.wave.ops.{list_signals, changes, changes_page, sample, sample_raw,
cut, info, detect_period}` (`changes` has no default limit; `changes_page` has the CLI's).

## Decisions

- The public Python API, CLI and MCP validate regexes, times and query bounds.
  Invalid arguments raise `WaveError`. CLI errors return exit 2. Invalid cut arguments
  preserve an existing output. Negative limits and sample times refuse the call.
  A zero change limit means no limit.
- Keep full VCD reference tokens, including escaped names and attached array indexes.
  Only separate tokens declare a bit range. Array elements keep distinct identities.
- Use one token reader for samples, changes, cuts, clocks, end times and handshakes.
  Support whitespace-separated scalar, binary, real and string changes, comments and
  standard dump directives. Invalid syntax or undeclared identifiers raise `WaveError`.
  Queries validate the part they read. End-time detection scans complete records.
- Capture raw VCD, gzip or FST bytes once per command before reading values. Nested
  Python operations share the capture scope. Independent API calls get separate captures.
  All reads and cuts use the private copy. Missing input refuses the command.
- Convert FST to a temporary disk file. Process-group handling owns cancellation.
  A converter failure raises `WaveError`. Validate converted output, including the
  single-timestamp `fst2vcd` form. Other incomplete directives still refuse the read.
  Conversion needs disk space and one full validation scan before the query.
- Resolve and identify each converter once. Check its captured bytes and metadata
  before returning output. Pin an oss-cad-suite `libexec` payload when present.
  Converters need no `--version`. Installed libraries stay stable under C8.
  The CLI buffers output until verification succeeds. Wave commands do not use a cache.
- VCD/FST simulator fixtures establish format handling. They do not validate a core.

## Performance

Time windows use non-negative bounds. The end must be at or after the start.
The Python API, CLI and MCP reject invalid bounds before opening a cut output.
Equal bounds select a single timestamp. An omitted end selects through the end of the wave.

VCD queries stream one pass and keep signal state. `changes` and `cut` stop after `--to`.
End-time detection scans the full file. Clock detection has a record limit. Earlier timing
numbers used the old line reader; the new reader has not been benchmarked on BOOM waves.

## Limit ownership

Indexed large-wave storage: [#173](https://github.com/riscPrint/risc-v-workstation/issues/173).

Retained limit: The documented query, sample and window bounds remain required. Unsupported formats or invalid times must refuse the call.

## Indexed snapshots

Build an index once, then pass its `.rvwi` path to the existing queries:

```sh
rvw wave index large.vcd -o large.rvwi --json
rvw wave changes large.rvwi 'unit.data' --from 1000000 --to 1000100 --json
rvw wave sample large.rvwi 'unit.data' --at end --json
rvw wave cut large.rvwi --from 1000000 --to 1000100 -o window.vcd
```

`--reader wellen` (default for FST when the `waves` extra is installed:
`uv pip install -e 'rvw[waves]'`) reads the wave with wellen, the Rust reader
Surfer uses, through pywellen. FST input is read natively, one signal at a time,
with no `fst2vcd` conversion. Up to 256 decoded signals stay in memory; a new
reader drops the previous batch. For VCD input wellen parses the whole file into
memory first, so the default VCD reader stays the streaming one.

Cached indexes: `--indexed` on any query (MCP `indexed: true`) keeps one index per
absolute wave path in `RVW_WAVE_INDEX_DIR` (default `~/.cache/rvw/wave-index`).
The index records the wave's size and mtime; when they differ, the query rebuilds
the index first. `rvw wave verify` compares the full SHA-256 for a stronger check.

The SQLite index stores raw values, aliases, declaration ranges, timescale,
ordered records and the captured input's SHA-256 and size. It is an explicit
snapshot. It does not follow changes to the source. Use a new output path to
index a new capture. An existing output is refused. The completed index is
published only after the strict parser reaches EOF and capture checks finish.
Keep published indexes immutable. Query transactions read the index directly;
they do not capture-copy it or scan/hash the original waveform.

SQLite uses disk indexes for time ranges and per-signal state lookup. A narrow
range visits that time window, including unselected signals in the window.
Samples use one indexed predecessor lookup per selected identifier. Cut writes
a temporary VCD containing the initial state and selected range. The existing
writer handles gzip/FST output. Unknown bits and real/string values stay raw in
the index. Repeated changes at the same time keep file order.

SQLite's page cache is limited to 8 MiB per connection. Build memory also includes
the header, one parser line, capture buffers and SQLite's index sorter. Query
memory includes the header and returned rows. `changes --limit 0` is unbounded.
The limit is a row limit, not a process memory cap. This format uses signed 64-bit
timestamps. Larger VCD times fail indexing. VCD, gzip and FST input use the current
reader during index creation. FST still needs a full `fst2vcd` conversion once.
Without pywellen, FST still needs one full `fst2vcd` conversion.

`test_wave_index.py` compares queries and cuts with the streaming reader. It
checks aliases, x/z bits, same-time updates, real/string values, empty ranges,
trailing timestamps, failed builds and SQL index selection. These fixture tests
do not establish performance for every large waveform.

Measure a large synthetic trace in separate build and query processes:

```sh
scripts/with-lock.sh suite nice -n 10 rvw/.venv/bin/python \
  scripts/benchmark-wave-index.py /tmp/wave-bench --rss-limit-mib 256
```

The default fixture has 524,288 changes to one 4096-bit signal. Its VCD is
2,153,664,099 bytes. The script checks the last ten values and reports peak
process RSS for each operation. It returns an error if measured RSS exceeds
the selected limit. This is a measured limit for this fixture, not an enforced
process allocation cap. Headers with many signals and longer tokens need
separate measurements.

Measured on this host (macOS arm64, `nice -n 10`): a synthetic 500-signal wave,
2.4 million records, 65 MB VCD / 9 MB FST. FST index build with the wellen
reader: 51 s wall, 145 MB peak RSS. The same through fst2vcd: 50 s, 145 MB.
SQLite insertion dominates both; wellen removes the converter and its temporary
VCD, not the insert cost. On that index, `find 'sig3 == sig4 || sig7[3:0] == 5'`
took 1.6 s and 48 MB RSS (the streamed VCD: 13.8 s, same 175 intervals);
`edges 'sig1$'` took 0.6 s.
