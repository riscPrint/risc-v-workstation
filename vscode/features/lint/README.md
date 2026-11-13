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

- The quick fix **Copy rvw lint waiver** copies an exact waiver row (config,
  rule, endpoint, `finding_id`) with a `TODO` reason. Write the reason and add the
  row to the settings `waivers` by hand; the feature does not edit settings.
- Structural findings point at the Scala declaration of the endpoint, not at the
  logic that causes the crossing.

## Rule tree

The Lint, CDC, RDC and SDC tree groups findings by rule. Open the same saved lint JSON or SARIF used by Problems. SDC backend findings use the same source jumps. Select a finding to open its recorded source line. The context menu copies an exact waiver through the existing waiver command. The Problems quick fix provides the same action. Add a reason before you put the waiver into settings. A finding without waiver identity gives an error. Backend not-run states remain in the status line. No waiver is applied automatically.
