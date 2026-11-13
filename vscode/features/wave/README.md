# Wave queries (VS Code feature)

Runs `rvw wave` queries and shows their JSON results in the **RVW Wave Query** view
(Explorer). The CLI and MCP tools do the work; this feature only runs them and displays
their output. See `rvw/src/rvw/wave/README.md` for each query's semantics.

| Command | What it does |
|---|---|
| Wave: New Query | Pick a kind (`find`, `edges`, `why`, `seq`, `txn`, `diff`, `changes`, `sample`), a wave and the arguments; runs it |
| Wave: Open Saved Query | Runs a saved `*.rvwq.json` query |
| Wave: Run Query Again / Save Query | Re-run the current query; save it as `*.rvwq.json` |
| Wave: Open Result JSON | Open the whole result, or the selected row, as JSON |
| Wave: Open Driver Location | On a `why` assignment row: open its database `file:line` |
| Wave: Jump to Signal Source via Design Database | On a signal row: `rvw query where`, then open the line only when the captured source hash matches |
| Wave: Open Debug Session | `rvw wave session open`: artifact status (ok, changed, missing), signals, cursors and embedded queries; an incomplete session shows a warning headline |
| Wave: Run Saved Query | On an embedded query row of a session: run it |
| Wave: Open Window in Surfer | On a row with a time (match, transfer, issue, divergence, `set_at`): `rvw wave cut` ±`wave.windowSpan` around it and open the cut in Surfer |

Saved query file (`rvw.wave-query/1`), paths relative to the file:

```json
{"schema": "rvw.wave-query/1", "kind": "why", "wave": "run/wave.vcd", "args": ["rob.rob_head"],
 "options": {"at": "1200c", "db": "design.db", "depth": 2}, "title": "ROB head at the hang"}
```

`args` are the positional arguments after the wave (expression, regex, signal, sequence, or
the second wave for `diff`). `options` are CLI options without dashes; `true` is a flag and
`false` is left out. Queries run with `execFile` and an argument array; no value goes through a
shell. Queries from **New Query** use `--indexed` (except `why`, which always uses the cached
index).

## Decisions

- Results are tool output. The view never shows a pass icon. Rows with `ambiguous`, `unknown`,
  `unresolved`, `diverged`, issues or failures get a warning icon. A `diff` match says "time
  alignment only"; no points compared is `inconclusive`.
- "Open Driver Location" uses the database location without a source-hash check and says so.
  "Jump to Signal Source" uses the checked `rvw query where` path shared with the result views.
- The wave/database pairing of a `why` query is the user's choice (`binding: unverified`).

## Limits

- No live cursor link to Surfer: "Open Window" writes a cut file and starts a new viewer.
- No in-view editing of results; open the JSON instead.
- Tested with unit tests of the model only (no VS Code host test).
