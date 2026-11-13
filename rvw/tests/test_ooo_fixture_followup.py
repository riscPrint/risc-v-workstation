"""Native fixture evidence must retain failures and consumer limits."""
import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast


def test_ooo_fixture_followup_keeps_native_controls_and_real_injection():
    root=Path(__file__).resolve().parents[2]/'SpinalChecks/examples/ooo'
    data=json.loads((root/'followup-results.json').read_text())
    variants={row['variant']:row for row in data['native']}
    assert len(variants)==8
    assert all(row['inserted']==68 for row in variants.values())
    assert not variants['clean']['firings']
    expected=dict(leak='freelist.conservation',double_allocate='freelist.allocate',
        commit_order='queue.order',not_ready='execution.operands',young_store='store.forward_age',
        stale_map='recovery.map',lost_flush='recovery.flush')
    for variant,kind in expected.items():
        assert any(row['kind']==kind for row in variants[variant]['firings'])
    assert data['conservation']['all_asserted']
    assert data['conservation']['activation_status']=='PASS'
    assert next(p for p in data['conservation']['proofs'] if p['job']=='depth16')['status']=='PASS'
    consumers=data['consumers']
    assert consumers['fault']['injected']==1 and consumers['fault']['counts']['detected']==1
    assert consumers['ooo_timing']['accuracy_status']=='inconclusive'
    assert consumers['probes_to_perf']['conversion']['retired']==consumers['ooo_timing']['instret']
