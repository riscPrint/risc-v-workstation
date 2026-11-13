#!/usr/bin/env python3
"""Publish pytest JUnit counts and enforce the fast Python timing budget."""
import argparse
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET


def summarize(path, max_seconds=None):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    totals = {key: sum(int(s.get(key, '0')) for s in suites)
              for key in ('tests', 'failures', 'errors', 'skipped')}
    seconds = sum(float(s.get('time', '0')) for s in suites)
    passed = totals['tests'] - sum(totals[k] for k in ('failures', 'errors', 'skipped'))
    text = (f"Tests: {passed} passed, {totals['skipped']} skipped, "
            f"{totals['failures']} failed, {totals['errors']} errors; {seconds:.2f} s.")
    over_budget = max_seconds is not None and seconds >= max_seconds
    if max_seconds is not None:
        text += f" Fast Python target: < {max_seconds:g} s ({'FAIL' if over_budget else 'PASS'})."
    return text, int(over_budget or totals['failures'] or totals['errors'])


def details(path):
    root = ET.parse(path).getroot()
    packages = {}
    cases = list(root.iter('testcase'))
    for case in cases:
        parts = case.get('classname', 'unknown').split('.')
        if parts[0] in ('tests', 'rvw'):
            parts = parts[1:] or ['unknown']
        package = parts[0]
        if package.startswith('test_'):
            package = package[5:].split('_')[0]
        counts = packages.setdefault(package, dict(passed=0, failed=0, skipped=0))
        outcome = 'failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
        counts[outcome] += 1
    def clean(text):
        return str(text).replace('|', '/').replace('\n', ' ')
    lines = ['\n| Package | Passed | Failed | Skipped |', '|---|---:|---:|---:|']
    lines += [f"| {clean(package)} | {c['passed']} | {c['failed']} | {c['skipped']} |" for package, c in sorted(packages.items())]
    lines += ['\nSlowest tests:']
    for case in sorted(cases, key=lambda c: float(c.get('time', 0)), reverse=True)[:10]:
        lines.append(f"- {clean(case.get('classname', ''))}.{clean(case.get('name', ''))}: {float(case.get('time', 0)):.2f} s")
    reasons = sorted({c.find('skipped').get('message', 'no reason supplied') for c in cases if c.find('skipped') is not None})
    if reasons:
        lines += ['\nSkip reasons:'] + ['- ' + clean(reason) for reason in reasons]
    if not cases:
        lines += ['Counts by package and test timings are unavailable in this report.']
    return '\n'.join(lines)


def language_details(text, package):
    rows = []
    for passed, failed, skipped in re.findall(r'test result:.*? (\d+) passed; (\d+) failed; (\d+) ignored;', text):
        rows.append((int(passed), int(failed), int(skipped)))
    if not rows:
        node = {key: int(value) for key, value in re.findall(r'^# (pass|fail|skipped) (\d+)$', text, re.M)}
        if {'pass', 'fail', 'skipped'} <= node.keys():
            rows = [(node['pass'], node['fail'], node['skipped'])]
    if not rows:
        return 'Counts unavailable from this runner. No count is inferred.'
    passed, failed, skipped = (sum(row[i] for row in rows) for i in range(3))
    return (f'| Package | Passed | Failed | Skipped |\n|---|---:|---:|---:|\n'
            f'| {package} | {passed} | {failed} | {skipped} |\n'
            'Per-test timing is unavailable from this runner.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report')
    parser.add_argument('--max-seconds', type=float)
    args = parser.parse_args()
    text, code = summarize(args.report, args.max_seconds)
    text += "\n" + details(args.report)
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(text + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
