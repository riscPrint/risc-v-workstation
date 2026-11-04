# Integrated debug

Run `Debug: Open Integrated Session`. Select a SpinalDB database and an indexed
wave (`rvw wave index wave.vcd -o wave.rvwi`). Set `debug.python` and
`debug.rvwSource` (`rvw/src`) when Python cannot import this checkout.
The extension requires a trusted workspace before it starts Python.

The four panes share one backend session and one private database capture.
The block pane uses the existing SpinalBlocks engine. Its design comes from
`blocks.json` in that capture. The native wave pane reads the SQLite wave index.
No second elaboration runs. The header gives the database identity and the
wave identity. Selecting two files does not establish that they came from one run.
The view states this limit.

Enter a signal and an integer wave time. Press Jump. Select a wave event to
move the cursor. Select a source line or a Scala editor line to find its signals.
If a line has several signals, select one of the candidates. Select a block or
a trace location to make the same reverse lookup. Select a static driver or a
dynamic trace signal to jump back to its wave, source and block.

Source text appears only when the captured source hash matches. Old schemas
without source bindings cannot supply verified source text. Missing, stale,
pruned and unresolved mappings remain visible. The driver pane first shows
static assignments and conditions. This does not identify the active driver.

Press Trace active driver to run `spinaltrace-cli dyn-pdg` at the cursor.
The backend exports PDG and HGLDD from the same database capture. It checks the
original VCD against the wave index hash. The trace keeps the engine accuracy
fields and raw graph visible. Missing artifacts or probes cannot establish a
complete active trace. Tracing currently requires the original uncompressed
VCD. It reads that file in full and has a 60-second process timeout. Closing the
panel stops the backend and its running trace process group.

## Local web host

Build the extension. Run from the repository root:

```sh
PYTHONPATH=rvw/src python3 -m rvw.query.session --db design.db --wave wave.rvwi --web vscode/dist/debug
```

Open the printed loopback URL. This host uses the same four-pane bundle and
backend as VS Code. Stop it with Ctrl-C. It has no external service dependency.
It is a local debug host, not a multi-user service.

## Checks and limits

Run `npm run typecheck`, `npm run build` and `npm test` in `vscode`.
Run `npm run test:integration:debug` for the shared web UI in headless Chromium.
Set `CHROMIUM` if the browser is not in the local Playwright cache. This test adds
synthetic source and block data to the VexRiscv fixture. It does not test a live
VS Code window.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_session.py -q` at the root.
The committed fixture is a SQL dump of the VexRiscv VexTop database at
`rvw/out/vex.db` in the selected VexRiscv checkout. It has 1160 signals and no
PDG, HGLDD or blocks artifacts. The test wave is synthetic. These tests do not
establish live VexRiscv trace parity. Missing source files are valid fixture use.

The wave pane returns at most 500 changes for one signal per 100-time-unit
window. It uses the `(code, t, seq)` index and reads the preceding value.
Times stay decimal strings across the UI boundary. The viewport uses BigInt.
The signal catalogue and block artifact load at open. Very large catalogues
or diagrams can still delay the UI.

`test/benchmark.py` creates a dense multi-GB synthetic indexed store. Run it
through the suite lock with `nice -n 10`. It reports backend open and jump
latency. It does not measure index build throughput from a multi-GB RTL wave,
VS Code startup, browser rendering, cold-cache latency or active trace latency.
Set `RVW_DEBUG_BENCH_INDEX` to that generated index when running the browser
test to measure web navigation through wave rendering. This uses a synthetic
single-block diagram and a warm filesystem cache. Neither test establishes
real RTL trace performance or the latency of a live VS Code window.

## C1 wave binding

At open, the backend looks for `result.json` beside the original indexed wave.
It captures this file and validates C1. It requires an explicit `artifacts.wave`.
That path must resolve to the indexed wave source. It hashes the current wave
and compares its size and SHA-256 with the index. This reads the full wave once
when an adjacent C1 file declares it. It can delay opening a large capture.
The binding is retained for this session. Reopen the session to capture new results.

The fixed binding note and expandable C1 evidence stay visible during navigation.
Missing, invalid, stale or conflicting evidence gives `inconclusive`.
`bound` means only that the declared artifact bytes match the index. It does
not validate the simulation claim, run-set generation or database association.
The database-to-run association stays `unverified`. A C1 error or incomplete
result retains its status and cause even when its wave bytes match.

What-if editing, full database/run identity joins, persisted sessions, bus and
coverage overlays, and a Verdi task comparison remain open in #297 and #24.
Surfer's separate database-consumption checks remain open in #69.

Failed jumps clear old wave, source and dependency evidence. Late responses cannot
replace a newer selection. Press Enter in Signal or Time to jump. Pane regions
have accessible names. Keyboard focus remains visible in both hosts.
