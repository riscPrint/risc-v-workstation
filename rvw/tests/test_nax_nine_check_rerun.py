"""The replacement ISA record must cover every current Nax declaration."""
import hashlib
import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast


def test_nax_rerun_has_nine_captured_checks_on_all_programs():
    root=Path(__file__).resolve().parents[2]
    example=root/'examples/naxriscv'
    data=json.loads((example/'checks-nine-rerun.json').read_text())
    spec=example/'rvw/micro-checks.json'
    assert data['spec_sha256']==hashlib.sha256(spec.read_bytes()).hexdigest()
    assert data['private_source_clean']
    assert len(data['declarations'])==len(data['generated']['rules'])==9
    assert data['generated']['complete']
    old=json.loads((example/'rvw/plants/check-results.json').read_text())
    assert {r['program'] for r in data['runs']}=={r['test'] for r in old['isa']['tests']}
    assert len(data['runs'])==data['pass_count']==59
    assert all(r['status']=='pass' and r['checks']['status']=='pass' and r['checks']['capture']
        and r['checks']['inserted']==9 and r['checks']['fired']==0 for r in data['runs'])
