"""Base-I selections retain the declared ISA in architecture/component models."""
import json
from pathlib import Path
import runpy
import pytest
from rvw.arch import sched
pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('isa', ['rv32i', 'rv64i'])
@pytest.mark.parametrize('kind', ['minor', 'timing'])
def test_architecture_base_i(isa, kind):
    model = runpy.run_path(str(ROOT / 'Arch/model.py'))
    d = json.loads((ROOT / 'Arch/reference/vexriscv-class.json').read_text())
    d.update(isa=isa, kind=kind, cpu={}, queues=[], predictor=None, icache=None, dcache=None)
    d.pop('ooo', None)
    model['validate_description'](d)
    assert d['isa'] == isa


@pytest.mark.parametrize('isa', ['rv32i', 'rv64i'])
def test_component_scheduling_base_i(tmp_path, isa):
    d = json.loads((ROOT / 'examples/vexriscv/sched/rv32im.json').read_text())
    d['isa'] = isa
    # Base I has no multiply class. The project supplies the actual resources.
    d['classes'] = d['classes'][:1]
    d['resources'] = {d['classes'][0]['resource']: 1}
    path = tmp_path / 'description.json'
    path.write_text(json.dumps(d))
    assert sched.description(path)['isa'] == isa


@pytest.mark.parametrize('isa,expected', [('rv32i','ilp32'), ('rv64i','lp64'), ('rv64gc','lp64d')])
def test_build_abi_fits_extensions(isa, expected):
    from rvw.arch.core import build_abi
    assert build_abi(isa) == expected
