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
```

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
