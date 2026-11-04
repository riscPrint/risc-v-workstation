"""Static C3/C4/history view. Gate acceptance does not imply verification closure."""
import html
import json
import math
from pathlib import Path
from rvw.regress.store import read_index
from rvw.results import find_results, load_verdict


def dashboard(root, output, *, core=None, suite=None, config=None, gate=None, run=None):
    rows = []
    trends = {}
    filters = dict(core=core, suite=suite, config=config, gate=gate, run=run)
    selected = []
    for entry in read_index(Path(root)):
        if run is not None and run not in entry.get('run_id', ''):
            continue
        if core is not None and entry.get('core') not in (None, core):
            continue
        path = Path(entry['path'])
        try:
            suites = find_results(path)
            suites = [s for s in suites if (core is None or s.core == core)
                      and (suite is None or s.suite == suite)
                      and (config is None or s.config == config)]
            if not suites and any(v is not None for v in (core, suite, config)):
                continue
            verdict = load_verdict(path / 'verdict.json').verdict if (path / 'verdict.json').exists() else 'not recorded'
        except (OSError, ValueError):
            suites, verdict = None, 'inconclusive'
        if gate is None or verdict == gate:
            selected.append((entry, suites, verdict))
    entries = [entry for entry, _, _ in selected]
    for index, (entry, suites, verdict) in enumerate(selected):
        path = Path(entry["path"])
        try:
            if suites is None:
                raise ValueError("missing or invalid evidence")
            counts = {}
            for suite in suites:
                samples = {"pass_rate": (sum(t.conclusive and t.status == "pass" for t in suite.tests) / len(suite.tests)) if suite.tests else None}
                wall = [getattr(t, "wall_s", None) for t in suite.tests]
                valid = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
                samples["run_time_s"] = sum(wall) if wall and all(valid(v) for v in wall) else None
                for metric in ("ipc", "coverage", "sim_khz", "sim_instructions_per_s"):
                    values = [test.metrics.get(metric) for test in suite.tests if test.conclusive and test.status == "pass"]
                    samples[metric] = sum(values) / len(values) if values and all(valid(v) for v in values) else None
                for metric, value in samples.items():
                    if value is not None:
                        trends.setdefault((suite.core, suite.suite, suite.config, metric), {})[index] = value
            for suite in suites:
                for test in suite.tests:
                    state = test.status if test.conclusive else "inconclusive"
                    counts[state] = counts.get(state, 0) + 1
            state = json.dumps(counts, sort_keys=True)
        except (OSError, ValueError):
            verdict, state = "inconclusive", "missing or invalid evidence"
        rows.append("<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in
                    (entry.get("run_id", "unknown"), entry.get("core", "unknown"), verdict, state)) + "</tr>")
    page = '<!doctype html><meta charset="utf-8"><title>Regression history</title><h1>Regression history</h1><p>Gate acceptance is separate from verification closure. Pass rate uses all recorded C3 tests as its denominator, including inconclusive tests. Run time is the sum of all recorded test wall_s values. IPC, coverage and simulation speed use recorded C3 metrics. Speed is grouped by preset and includes adapter execution and artifact handling. Missing metrics are not zero. Coverage compatibility and verification closure are not established by this report.</p><table><thead><tr><th>Run</th><th>Core</th><th>Gate</th><th>C3 results</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    page += '<p>Filters: ' + html.escape(json.dumps({k: v for k, v in filters.items() if v is not None}, sort_keys=True)) + '</p>'
    page += '<p>Missing evidence stays visible when suite or config cannot be checked.</p>'
    for key, samples in sorted(trends.items()):
        high = max(samples.values()) or 1
        page += '<h2>' + html.escape(" / ".join(key)) + '</h2><svg role="img" aria-label="Recorded metric samples, oldest first" viewBox="0 0 400 100" width="400">'
        previous = None
        for index, value in sorted(samples.items()):
            x, y = 10 + index * 380 / max(1, len(entries)-1), 90 - value * 80 / high
            if previous is not None and index == previous[0] + 1:
                page += f'<line x1="{previous[1]:.2f}" y1="{previous[2]:.2f}" x2="{x:.2f}" y2="{y:.2f}" stroke="blue"/>'
            page += f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3"><title>' + html.escape(str(entries[index].get('run_id', 'unknown')) + ': ' + str(value)) + '</title></circle>'
            previous = (index, x, y)
        page += '</svg><table><tr><th>Run (oldest first)</th><th>Value</th></tr>'
        for index, entry in enumerate(entries):
            page += '<tr><td>' + html.escape(str(entry.get('run_id', 'unknown'))) + '</td><td>' + html.escape(str(samples.get(index, 'not recorded'))) + '</td></tr>'
        page += '</table>'
    if not trends:
        page += '<p>Coverage and IPC metrics: not recorded.</p>'
    Path(output).write_text(page)
    return {"file": str(output), "runs": len(rows), "filters": filters}
