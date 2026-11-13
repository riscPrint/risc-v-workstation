"""Exercise pooled elasticity and tie reporting without rerunning model timing."""
import json
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast


def test_resource_summary_uses_saved_per_pair_values():
    root = Path(__file__).resolve().parents[2]
    summarize = runpy.run_path(str(root/'examples/naxriscv/rvw/arch/resource-study.py'))['summarize']
    cfg = {'rob_entries': 64, 'issue_entries': 32}
    cal = {'samples': {'training': [dict(id='a', ipc_error_percent=-10, rtl_ipc=1, model=dict(ipc=.9, config=cfg))],
                       'heldout': [dict(id='b', ipc_error_percent=20, rtl_ipc=1, model=dict(ipc=1.2, config=cfg))]}}
    common = dict(program='a', measured_delta=0, predicted_delta=0, wrong_delta=False, absolute_error_pp=0,
                  rtl_base_ipc=1, rtl_variant_ipc=1, model_base=dict(instret=10, cycles=10, engine_sha256='test'),
                  model_variant=dict(cycles=10), hashes={}, base_hashes={})
    report = dict(variants=[dict(id='rob',changes={'rob_entries':128}),dict(id='iq',changes={'issue_entries':16})],
                  rows=[dict(common,variant='rob'),dict(common,variant='iq')])
    summary = summarize(cal, report)
    assert summary['within'] == 2 and summary['nonzero_within'] == 0
    assert summary['absolute']['training']['mae_percent'] == 10
    assert summary['absolute']['heldout']['mae_percent'] == 20
    assert summary['rank']['kendall_tau_b'] is None
