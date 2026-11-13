"""Retain all historical firing events and their new native dispositions."""
from collections import Counter
import json
from pathlib import Path
import pytest
pytestmark = pytest.mark.fast


def test_vexii_firing_dispositions_cover_all_events():
    root = Path(__file__).resolve().parents[2]
    report = json.loads((root/'examples/vexiiriscv/checks-evidence/firing-triage.json').read_text())
    counts = Counter()
    for run in report['historical_programs']:
        for firing in run['firings']:
            counts[firing['id']] += firing['count']
    assert sorted(counts.values()) == [36, 103]
    assert {row['id'] for row in report['checks']} == set(counts)
    assert all(row['samples'] and row['source'] for row in report['checks'])
    rerun = report['rerun']
    assert len(rerun['results']) == rerun['programs'] == 51
    assert all(r['status']=='pass' and r['fired']==0 for r in rerun['results'])
