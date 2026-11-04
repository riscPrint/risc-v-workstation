#!/usr/bin/env python3
"""Publish pytest JUnit counts and enforce the fast Python timing budget."""
import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def summarize(path, max_seconds=None):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    totals = {key: sum(int(s.get(key, '0')) for s in suites)
              for key in ('tests', 'failures', 'errors', 'skipped')}
    seconds = sum(float(s.get('time', '0')) for s in suites)
    passed = totals['tests'] - sum(totals[k] for k in ('failures', 'errors', 'skipped'))
    text = (f"Python tests: {passed} passed, {totals['skipped']} skipped, "
            f"{totals['failures']} failed, {totals['errors']} errors; {seconds:.2f} s.")
    over_budget = max_seconds is not None and seconds >= max_seconds
    if max_seconds is not None:
        text += f" Fast Python target: < {max_seconds:g} s ({'FAIL' if over_budget else 'PASS'})."
    return text, int(over_budget or totals['failures'] or totals['errors'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report')
    parser.add_argument('--max-seconds', type=float)
    args = parser.parse_args()
    text, code = summarize(args.report, args.max_seconds)
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(text + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
