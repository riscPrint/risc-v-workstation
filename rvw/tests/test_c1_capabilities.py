import importlib.util
from pathlib import Path
import pytest
from rvw.regress.config import load_config, Suite
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.sim.backends import require_native


def test_c1_profile_does_not_claim_cocotb_callbacks():
    assert require_native('riscvsim-verilator', ['two_state', 'clock']).values == '2-state'
    for feature in ['four_state', 'vpi', 'read_only', 'sva', 'coverage']:
        with pytest.raises(ValueError, match=feature):
            require_native('riscvsim-verilator', [feature])


@pytest.mark.parametrize('backend', [None, 'riscvsim-verilator'])
def test_c1_refuses_before_input_capture_or_output(fake, tmp_path, backend):
    core = load_config(str(fake.config))
    core.backend = backend
    core.suites['isa'].requires = ['four_state']
    out = tmp_path / 'out'
    with pytest.raises(ValueError):
        Runner(core, describe(fake.repo), out, RunOptions(index=False, log=None))
    assert not out.exists()
    assert not fake.calls()


def test_project_load_negotiates_requirements(fake):
    text = fake.config.read_text().replace('[core]', '[core]\nbackend = "riscvsim-verilator"')
    text = text.replace('[suites.isa]', '[suites.isa]\nrequires = ["four_state"]')
    fake.config.write_text(text)
    with pytest.raises(ValueError, match='four_state'):
        load_config(str(fake.config))


@pytest.mark.parametrize('features', ['clock', [1], [True], ['']])
def test_malformed_requirements(features):
    with pytest.raises(ValueError):
        Suite('bad', requires=features)


def test_direct_native_entry_refuses_before_launch(monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'RiscvSim/scripts/supervise.py'
    spec = importlib.util.spec_from_file_location('supervise_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv('RISCVSIM_REQUIRES', 'four_state')
    monkeypatch.setattr(mod.tempfile, 'mkdtemp', lambda **kw: pytest.fail('created launch output'))
    monkeypatch.setattr(mod, 'run_group', lambda *a, **kw: pytest.fail('started tools'))
    assert mod.supervise('/bin/bash', '/absent', ['run']) == 2


def test_independent_plan_cannot_bypass_capabilities(fake, tmp_path):
    from rvw.regress.plan import PlanItem
    core = load_config(str(fake.config))
    out = tmp_path / 'out'
    with Runner(core, describe(fake.repo), out, RunOptions(index=False, log=None)) as runner:
        with pytest.raises(ValueError):
            runner.run([PlanItem(Suite('foreign', requires=['four_state']), 'small')])
    assert not out.exists()
    assert not fake.calls()
