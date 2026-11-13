# Lint feature

Shows `rvw lint` findings as VS Code diagnostics (Problems panel).

| Command | What it does |
|---|---|
| **Lint: Run rvw lint** | Runs `rvw lint --settings FILE --json` with `lint.settings` (or asks for the file) and shows the findings. |
| **Lint: Run Again** | Runs the last settings file again. |
| **Lint: Open Saved Report or SARIF** | Shows a saved `rvw.lint/1` report or a SARIF 2.1.0 log (`rvw lint --sarif`). |
| **Lint: Clear Diagnostics** | Removes the diagnostics. |

Each diagnostic has the rule as its code and `rvw lint <backend>` as its source.
Findings with a file and line (Scala source from SpinalDB, RTL `file:line:col`
from native lint) go to that line. Findings without a location go to line 1 of
the settings file or the opened report. Waived findings are hints with their
waiver reason. Stale waivers are errors. The status bar shows the report status,
active and waived counts, and backends that did not run. It never shows clean
unless the report status is `clean`.

Settings: `lint.rvwExecutable`, `lint.settings`, `lint.timeoutMs`. Running rvw
needs a trusted workspace.

## Decisions

- Parsing is in `src/model.ts` (no VS Code API), so unit tests cover it.
- The feature shows results. It does not judge them; the report status stays as
  `rvw lint` wrote it.

## Limits

- No quick fixes or waiver editing yet; add waivers to the settings file by hand
  with the finding `id`.
- Structural findings point at the Scala declaration of the endpoint, not at the
  logic that causes the crossing.
