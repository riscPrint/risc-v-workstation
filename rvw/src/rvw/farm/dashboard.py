"""Static C3/C4/history view. Gate acceptance does not imply verification closure."""
import html
import json
import math
from pathlib import Path
from rvw.regress.store import read_index
from rvw.results import find_results, load_verdict


def dashboard(root, output):
    rows = []
    trends = {}
    for entry in read_index(Path(root)):
        path = Path(entry["path"])
        try:
            suites = find_results(path)
            verdict = load_verdict(path / "verdict.json").verdict if (path / "verdict.json").exists() else "not recorded"
            counts = {}
            for suite in suites:
                for metric in ("ipc", "coverage"):
                    values = [test.metrics.get(metric) for test in suite.tests if test.conclusive and test.status == "pass"]
                    if values and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in values):
                        trends.setdefault((suite.core, suite.suite, suite.config, metric), []).append(sum(values) / len(values))
            for suite in suites:
                for test in suite.tests:
                    state = test.status if test.conclusive else "inconclusive"
                    counts[state] = counts.get(state, 0) + 1
            state = json.dumps(counts, sort_keys=True)
        except (OSError, ValueError):
            verdict, state = "inconclusive", "missing or invalid evidence"
        rows.append("<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in
                    (entry.get("run_id", "unknown"), entry.get("core", "unknown"), verdict, state)) + "</tr>")
    page = '<!doctype html><meta charset="utf-8"><title>Regression history</title><h1>Regression history</h1><p>Gate acceptance is separate from verification closure. Trends use only recorded C3 metrics named ipc and coverage. Missing metrics are not zero. Coverage compatibility and verification closure are not established by this report.</p><table><thead><tr><th>Run</th><th>Core</th><th>Gate</th><th>C3 results</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    for key, values in sorted(trends.items()):
        high = max(values) or 1
        points = " ".join(f"{10 + i * 380 / max(1, len(values)-1):.2f},{90 - value * 80 / high:.2f}" for i, value in enumerate(values))
        page += '<h2>' + html.escape(" / ".join(key)) + '</h2><svg role="img" aria-label="Recorded metric samples" viewBox="0 0 400 100" width="400"><polyline fill="none" stroke="blue" points="' + points + '"/></svg><p>' + html.escape(json.dumps(values)) + '</p>'
    if not trends:
        page += '<p>Coverage and IPC metrics: not recorded.</p>'
    Path(output).write_text(page)
    return {"file": str(output), "runs": len(rows)}
