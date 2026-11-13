"""Current evidence cannot turn misses or stress failures into clean passes."""
import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast


def test_current_activation_partition_keeps_newly_inactive_divider():
    root=Path(__file__).resolve().parents[2]
    report=json.loads((root/'SpinalChecks/current-results.json').read_text())
    assert sum(r['combined_activated'] for r in report['designs'])==63
    assert sum(len(r['unreachable']) for r in report['designs'])==13
    assert sum(len(r['no_activation']) for r in report['designs'])==6
    for row in report['designs']:
        assert row['bound']==row['combined_activated']+len(row['unreachable'])+len(row['no_activation'])
        assert row['stress_firings'] and row['clean_firings']==0
        assert row['bound']==row['formal_reached']+row['formal_unreachable']+row['formal_unresolved']
    vexii=next(r for r in report['designs'] if r['core']=='vexiiriscv')
    assert 'stream.valid_hold:early0_DivPlugin_logic_processing_div.io_rsp' in vexii['no_activation']
    assert all(r['status']=='UNKNOWN' for r in report['responder_proofs'])
