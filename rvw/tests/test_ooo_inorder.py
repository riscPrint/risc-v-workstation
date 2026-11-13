"""In-order issue must retain an older blocked operation at the queue head."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from rvw.ooo.core import Config, Instruction, simulate
from rvw.ooo.project import configuration
from rvw.ooo.native import supported

pytestmark = pytest.mark.fast


def test_inorder_does_not_bypass_dependency():
    base = Config(4, 8, 4, 16, 1, 8, 2, 2, 1,
                  {'alu': 1, 'load': 8, 'multiply': 6})
    ops = [Instruction('load', dest=1), Instruction('alu', (1,), 2),
           Instruction('multiply', dest=3)]
    ooo = simulate(ops, base, backend='python')
    ordered = simulate(ops, replace(base, issue_order='in_order'), backend='python')
    assert ordered['cycles'] > ooo['cycles']
    assert ordered['instret'] == ooo['instret'] == 3
    assert not supported(replace(base, issue_order='in_order'))
    with pytest.raises(ValueError, match='issue_order'):
        replace(base, issue_order='other')


@pytest.mark.parametrize('name', ['vexriscv', 'vexiiriscv'])
def test_minor_project(name):
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / f'examples/{name}/rvw/arch/own.json').read_text())
    c = configuration(data)
    assert c.issue_order == 'in_order' and c.issue_width == c.commit_width == 1
    data['ooo']['issue_width'] = 2
    with pytest.raises(ValueError, match='conflicts'):
        configuration(data)


def test_ipc_only_calibration(tmp_path):
    from test_ooo_evidence import inputs
    from rvw.ooo.evidence import calibrate
    plan, _ = inputs(tmp_path)
    (tmp_path / 'map').write_text('{}')
    result = calibrate(plan, tmp_path / 'ipc-only')
    assert result['correlations'] == {}
    assert not result['budgets']['sufficient_coverage']
    assert not result['budgets']['observed_events_within_budget']
    assert result['samples']['heldout'][0]['ipc_error_percent'] is not None


def test_inactive_irq_declaration(tmp_path):
    from test_ooo import trace
    from rvw.ooo.core import _instructions
    t = tmp_path / 'trace'
    trace(t, step=2)
    lines = t.read_text().splitlines()
    lines.insert(1, json.dumps(dict(event='irq', cycle=0, levels='0x0')))
    assert len(_instructions(('\n'.join(lines)+'\n').encode())) == 4
    lines[1] = json.dumps(dict(event='irq', cycle=0, levels='0x80'))
    with pytest.raises(ValueError, match='interrupts'):
        _instructions(('\n'.join(lines)+'\n').encode())
