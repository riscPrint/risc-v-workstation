"""Keep committed activation evidence distinct from engine-only passes."""
import json
import os
from pathlib import Path
import pytest

pytestmark=pytest.mark.fast
ROOT=Path(os.environ.get('RVW_RAW_EVIDENCE_ROOT', Path(__file__).resolve().parents[2]))/'SpinalChecks'


def test_campaign_cannot_count_unactivated_engine_passes():
    report=json.loads((ROOT/'activation-results.json').read_text())
    if report.get('summary_only'):
        pytest.skip('Raw activation campaign data is not tracked. Regenerate the full campaign outside the repository and set RVW_RAW_EVIDENCE_ROOT to its parent directory to run this evidence check.')
    for design in report['designs']:
        q=design['qualification']
        inserted={c['id'] for c in design['inventory']['checks'] if c['status']=='inserted'}
        assert {a['id'] for a in q['activation']}==inserted
        for row in q['counts'].values():
            assert row['bounded'] <= row['activated_formal']
            assert row['proven'] <= row['activated_formal']
        assert design['formal_complete']
        assert len(design['formal_observations'])==len(inserted)
    vexii=next(d for d in report['designs'] if d['core']=='vexiiriscv')
    assert vexii['qualification']['status']=='findings'
    assert vexii['c1_status']['fail']==49


def test_induction_samples_retain_portfolio_refusal():
    report=json.loads((ROOT/'activated-induction-results.json').read_text())
    assert report['scope']=='selected instances only'
    for row in report['rows']:
        assert len(row['properties'])==1
        assert row['properties'][0]['formal_status']=='proven'
        assert row['properties'][0]['activation']['status']=='reached'
        assert row['portfolio']['status']=='inconclusive'
        assert row['portfolio']['proof_kind']=='none'


def test_kind_samples_do_not_promote_proven_but_inactive_rules():
    report=json.loads((ROOT/'kind-induction-results.json').read_text())
    for row in report['rows']:
        prop=row['property']
        assert row['sampled']==1 <= row['bound_instances']
        assert row['passing_conditional_evidence']==(
            prop['formal_status']=='proven' and prop['activation']['status']=='reached')
    inactive=[r for r in report['rows'] if r['property']['formal_status']=='proven'
              and r['property']['activation']['status']=='not_reached_within_bound']
    assert inactive and all(not r['passing_conditional_evidence'] for r in inactive)
