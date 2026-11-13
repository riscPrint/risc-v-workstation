#!/usr/bin/env python3
"""Retain JUnit reports before the isolated CI work directory is removed."""
from pathlib import Path
import shutil
import sys


def copy_reports(source, destination):
    source, destination = Path(source), Path(destination)
    reports = list(source.glob('*results.xml')) + list(source.glob('ci-*.log')) + list(source.glob('**/target/test-reports/*.xml'))
    for report in reports:
        target = destination / report.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report, target)
    return len(reports)


if __name__ == '__main__':
    copy_reports(*sys.argv[1:])
