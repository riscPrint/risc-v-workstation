"""Project benchmark tiers stay opt-in and use the existing gate policy."""
from dataclasses import replace
from pathlib import Path
import pytest
from rvw.regress.config import load_config
from rvw.regress.discover import discover
from rvw.regress.cli import execute_json
pytestmark = pytest.mark.fast


@pytest.mark.parametrize('name', ['vexriscv','vexiiriscv','naxriscv','ooo-mini','picorv32'])
def test_opt_in_project_tier(name, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    for key in ('VEXRISCV','VEXIIRISCV','NAXRISCV','RVW_CORE_SOURCE'):
        monkeypatch.setenv(key,str(tmp_path))
    monkeypatch.setenv('RVW_HOME',str(root))
    monkeypatch.setenv('RVW_VEX_LOCK','vex-bench')
    monkeypatch.setenv('RVW_NAX_LOCK','nax-bench')
    monkeypatch.setenv('RVW_OOO_LOCK','ooo-mini-bench')
    monkeypatch.setenv('RVW_CORE_LOCK','picorv32-bench')
    cfg=load_config(project=root/'examples'/name)
    assert cfg.perf_tolerance == .01
    assert cfg.tiers['bench'].runs[0].suite == 'bench'
    for tier in ('quick','full'):
        if tier in cfg.tiers:
            assert all(r.suite != 'bench' for r in cfg.tiers[tier].runs)
    suite=cfg.suites['bench']
    assert suite.perf_metrics == ['cycles']
    assert cfg.lock.endswith('-bench')
    programs=tmp_path/'programs';programs.mkdir()
    for program in ('median','vvadd','multiply','qsort'):
        (programs/program).mkdir();(programs/program/'workload.elf').write_bytes(b'ELF')
    assert [p.id for p in discover(replace(suite,dir=programs))] == ['median','multiply','vvadd']


def test_gate_rejects_a_committed_cycle_regression(fake, tmp_path):
    # Fixture evidence tests the real gate path; no native performance is claimed.
    fake.config.write_text(fake.config.read_text().replace('[suites.isa]', '[suites.isa]\nperf_metrics = ["cycles"]'))
    base=fake.commit({'rv64ui-p-add':'cycles=100','rv64ui-p-sub':'cycles=100'},'baseline')
    candidate=fake.commit({'rv64ui-p-add':'cycles=102','rv64ui-p-sub':'cycles=100'},'slower')
    verdict=execute_json('gate',core=str(fake.config),tier='quick',base_rev=base,cand_rev=candidate,
                         out=str(tmp_path/'gate'),no_cache=True,no_index=True,perf_tolerance=.01)
    assert verdict['verdict'] == 'reject'
    assert not verdict['new_failures']
    assert any(r['regression'] for r in verdict['perf'])
