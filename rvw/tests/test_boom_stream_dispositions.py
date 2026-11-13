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
    assert report['historical_named_dispositions'] + report['unmapped_historical_checks'] == 24
    assert report['source_dispositions'] == report['historical_named_dispositions'] + len(report['later_aliases'])


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


def test_internal_source_offset_stage_has_a_separate_source_disposition():
    root = ROOT/'SpinalChecks/boom'
    report = runpy.run_path(str(root/'stream-dispositions.py'))['dispositions']()
    rows = {r['id']: r for r in report['checks']}
    ident = 'stream.payload_stable:arbiter.ups_0_a'
    assert ident in rows and 'stream.payload_stable:arbiter.io_ups_0_a' in rows
    assert rows[ident]['mechanism'] == 'tilelink_pre_acceptance_offer'
    assert rows[ident]['cancel_condition'] is None
    assert 'Bus.scala:456-465' in rows[ident]['reason']
    assert ident not in (root/'streams.txt').read_text()
    assert ident not in (root/'waivers.txt').read_text()
    assert report['unmapped_historical_checks'] > 0  # The later alias cannot close the original inventory.
