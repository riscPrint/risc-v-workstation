"""Keep reached triggers, unreachability proofs and misses separate."""
import json
import os
from pathlib import Path
import pytest
pytestmark = pytest.mark.fast
ROOT = Path(os.environ.get('RVW_RAW_EVIDENCE_ROOT', Path(__file__).resolve().parents[2]))


def test_followup_covers_every_original_inactive_check():
    old=json.loads((ROOT/'SpinalChecks/activation-results.json').read_text())
    new=json.loads((ROOT/'SpinalChecks/activation-followup-results.json').read_text())
    if old.get('summary_only'):
        pytest.skip('Raw activation campaign data is not tracked. Regenerate the full campaign outside the repository and set RVW_RAW_EVIDENCE_ROOT to its parent directory to run this evidence check.')
    for before,after in zip(old['designs'],new['designs']):
        assert after['core']==before['core']
        expected={a['id'] for a in before['qualification']['activation'] if a['simulation_status']=='no_activation'}
        assert {r['id'] for r in after['decisions']}==expected
        assert len(after['formal'])==sum(c['status']=='inserted' for c in before['inventory']['checks'])
        for row in after['decisions']:
            if row['decision']=='unreachable':
                assert row['formal']['unreachable_status']=='PASS'
                assert any('Temporal induction successful' in line for line in row['formal']['unreachability_proof'])
            elif row['decision']=='activated':
                assert row['simulation_count']>0
            else:
                assert row['decision']=='no_activation' and row['simulation_count']==0
    assert all(s['applicable'] for s in new['suite_plan']['suites'])
