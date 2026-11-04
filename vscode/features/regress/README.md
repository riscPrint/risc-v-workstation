# RVW Regression

Show saved rvw results in the VS Code Explorer. This feature is part of #24.
Owner decision #77 remains open.

## Use

1. Write a JSON report with rvw. For example:

   ```sh
   rvw regress compare BASE CANDIDATE --json > verdict.json
   ```

2. Run **Regression: Open Report** from the Command Palette.
3. Expand **Report** in **RVW Regression** to read all fields.
4. Use the view menu to refresh the file or open the raw JSON.

Supported schemas: `rvw.results/1` (C3) and `rvw.verdict/2` (C4).
Other schemas give an error. An invalid refresh clears the previous result.
No file watcher runs. Refresh after the producer writes a new report.

All report fields stay available. This includes scope, identities, verdict causes,
unchanged failures, incomplete evidence, bins, holes, exclusions, attribution confidence,
unsupported observations, perf warnings and measurement limits when the producer supplies them.
A missing field stays missing. The view does not infer it.

## Navigation

Each view menu has these commands. They also appear in the Command Palette.

- **Jump to Source via Design Database**: select the captured database for the run.
  Enter a signal path. The extension runs `rvw query where --db DB --json -- SIGNAL`.
  It shows a source choice for groups. It opens only a source with a captured hash.
  It checks that hash again before opening the Scala line.
- **Open Waveform in Surfer**: select a VCD, compressed VCD or FST file.
- **Open SpinalTrace**: select `pdg.json` and a waveform. Enter a criterion such as
  `signal:io.result`, `statement:connect_io_result` or `line:Unit.scala:42`.
  SpinalTrace uses the end of the waveform. Its recorded PDG settings supply other defaults.

Install the native tools and put them on PATH. Set `regress.rvwExecutable`,
`regress.surferExecutable` and `regress.spinaltraceExecutable` for other executable paths.
These settings are executable names or paths, not shell command strings.
Native tools need a trusted workspace. Surfer and SpinalTrace use VS Code process tasks.
Their task terminal shows launch failures. The query has a 30-second timeout.
Query failures and unresolved, pruned or stale mappings give an error.
The RISC-V Workstation output channel retains the full query result.

## Decisions

- Read saved producer data. Do not rerun tests, compute verdicts or validate run-set generations.
- Use text and warning icons. Never use a green acceptance icon.
  An inconclusive verdict remains inconclusive even when its `tests` field says `pass`.
- Keep event IPC and coverage observations separate from correctness verdicts.
- Use the database's captured source hash for source jumps. Do not open `stored_loc`
  as current source. Reject database warnings and pruned mappings.
- Select the database, wave and PDG explicitly. The user must select matching artifacts.
  The feature does not prove that these artifacts belong to the displayed report.
- Use native process argument arrays. Do not build shell commands from paths or criteria.

## Tests

From `vscode/`:

```sh
npm run typecheck && npm run build && npm test
```

Fixture tests check retained evidence and incomplete results. Shared host tests check
loading, failed refresh, warning colors, native task arguments and workspace trust.
Source tests check captured locations, stale and pruned mappings, and changed source hashes.
These are unit tests. They do not establish native viewer or VS Code desktop behavior.

## Known limits

This is a saved-report viewer with manual navigation. It has no run queue, cancellation,
progress tracking, automatic report discovery or report-to-database identity binding.
Coverage file/line attribution stays visible as producer data. To jump through the captured
database, enter the associated signal path. File/line-only coverage points have no automatic
reverse lookup. Reports without signal paths require the user to supply one.
Bidirectional navigation, run alignment, bus decoding, proof panels, software debugging
and portable sessions remain in #24. This feature does not decide #77.

## Selected evidence

Use **Open Selected Evidence** in a result row's context menu to read its full
JSON in an editor. Use **Jump to Source via Design Database** on a row with an
explicit `signal` field. It uses that signal without another text entry. The
database choice and captured source hash checks still apply. A generic `path`
field is not treated as a signal.

Use **Open Declared C1 Run Result** on a job row with a `run` field. Relative
paths resolve from the suite report directory. The command opens that run's
`result.json` directly. A missing file gives an error. It does not fall back to
another run or validate generation ownership. The saved suite stays in the tree.
