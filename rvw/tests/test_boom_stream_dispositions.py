"""Keep the source-only disposition report reproducible and conservative."""
import json
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_source_report_is_current_and_does_not_claim_native_results():
    root = ROOT / 'SpinalChecks/boom'
    regenerate = runpy.run_path(str(root / 'stream-dispositions.py'))['dispositions']
    report = json.loads((root / 'stream-dispositions.json').read_text())
    assert report == regenerate()
    assert report['native_validation'] == 'NOT RUN'
    assert report['generic_cancellation_explained'] == 0
    assert len({r['id'] for r in report['checks']}) == report['source_dispositions']
    assert report['source_dispositions'] + report['unmapped_historical_checks'] == 24


def test_live_payload_and_per_cycle_offers_do_not_become_cancel_bindings():
    report = runpy.run_path(str(ROOT/'SpinalChecks/boom/stream-dispositions.py'))['dispositions']()
    rows = {r['id']: r for r in report['checks']}
    stable = rows['stream.payload_stable:tile.dcache.mshrs.mshrs_1.rpq.io_deq']
    hold = rows['stream.valid_hold:tile.dcache.mshrs.mshrs_1.rpq.io_deq']
    assert stable['mechanism'] == 'live_branch_mask_update' and stable['cancel_condition'] is None
    assert hold['mechanism'] == 'registered_branch_kill_or_flush'
    assert 'head_uop' in hold['cancel_condition'] and hold['binding_validation'] == 'NOT RUN'
    assert rows['stream.valid_hold:tile.core.xcpt_pc_req']['cancel_condition'] is None
    for row in report['checks']:
        if row['explicit_binding']:
            assert row['cancel_condition'] == 'io_flush' and row['cancel_sample'] == 'previous'
