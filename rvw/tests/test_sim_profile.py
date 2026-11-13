import json

import pytest

from rvw.sim.profile import report


def test_recorded_costs_and_missing_measurements(tmp_path, monkeypatch):
    monkeypatch.setattr('rvw.sim.profile.shutil.which', lambda name: '/tool/verilator' if name == 'verilator' else None)
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(dict(schema='rvw.run/1', status='pass', cycles=1000, instret=500,
        details=dict(execution_s=2, model_timing=dict(elaboration_s=3, native_and_setup_s=4)))))
    data = report([path], build_profile='threads-4')
    assert data['tools']['arcilator']['status'] == 'not_installed'
    assert data['environment']['SPINAL_VERILATOR_FLAGS'] == '--threads 4'
    row = data['runs'][0]
    assert row['sim_khz'] == 0.5 and row['instructions_per_s'] == 250
    assert row['native_and_setup_s'] == 4
    assert row['scala_compile_s'] is None and row['peak_rss_bytes'] is None
    assert data['status'] == 'reported' and data['qualification'].startswith('none')
    path.write_text(json.dumps(dict(schema='rvw.run/1', details=dict(execution_s=0))))
    assert report([path])['runs'][0]['sim_khz'] is None
    with pytest.raises(ValueError): report([], build_profile='unqualified-pgo')


def test_missing_timing_and_invalid_c1_cannot_become_measurements(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{"schema":"rvw.run/1","status":"error","cycles":false}')
    data = report([path])
    assert data['runs'][0]['cycles'] is None
    assert data['runs'][0]['execution_s'] is None
    assert data['profile_applied'] is False
    path.write_text('{"schema":"not-c1"}')
    with pytest.raises(ValueError, match='not a C1'): report([path])
