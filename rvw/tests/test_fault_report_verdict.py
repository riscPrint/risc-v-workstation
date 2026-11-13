"""CLI and MCP reports preserve incomplete campaign evidence."""
import json
from argparse import Namespace

import pytest

from rvw.fault import api, campaign, cli

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('classification,status,code', [
    ('safe', 'complete', 0), ('detected', 'complete', 0),
    ('silent_corruption', 'fail', 1), ('not_injected', 'inconclusive', 3),
    ('inconclusive', 'inconclusive', 3), ('timeout', 'inconclusive', 3),
])
def test_report_verdict_matches_evidence(tmp_path, capsys, classification, status, code):
    data = campaign.plan([dict(path='pipeline.state', width=1)], kinds=('flip',),
                         window=(1, 2), samples=1)
    outcomes = [dict(data['faults'][0], classification=classification, evidence={})]
    (tmp_path / 'plan.json').write_text(json.dumps(data))
    (tmp_path / 'outcomes.json').write_text(json.dumps(outcomes))
    assert api.report(tmp_path)['status'] == status  # Also used by MCP.
    assert cli._report(Namespace(directory=tmp_path)) == code
    assert json.loads(capsys.readouterr().out)['status'] == status


def test_silent_corruption_takes_priority_over_missing_evidence():
    data = campaign.plan([dict(path='pipeline.state', width=2)], kinds=('flip',),
                         window=(1, 2), samples=2)
    outcomes = [dict(data['faults'][0], classification='silent_corruption', evidence={})]
    assert campaign.report(data, outcomes)['status'] == 'fail'


def test_empty_campaign_is_inconclusive():
    data = campaign.plan([dict(path='pipeline.state', width=1)], kinds=('flip',),
                         window=(1, 2), samples=0)
    assert campaign.report(data, [])['status'] == 'inconclusive'
