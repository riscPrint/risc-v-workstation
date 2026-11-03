"""Test-source selection and C1 dispatch. Fixtures do not prove ISA behavior."""
from pathlib import Path

import pytest

from rvw.regress.config import load_config
from rvw.regress.discover import discover
from rvw.results import load_results


@pytest.mark.parametrize('config', ['rvw/configs/boom.toml', 'examples/boom/rvw.toml'])
def test_vm_sources_use_private_core_and_exclude_dumps(config, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv('RVW_HOME', str(root))
    monkeypatch.setenv('SPINAL_BOOM', str(tmp_path))
    monkeypatch.delenv('VM_TESTS', raising=False)
    suite = load_config(str(root / config)).suite('vm-tests')
    assert suite.dir == root.parent / 'spinal-boom-eda/tests/vm/build'
    monkeypatch.setenv('VM_TESTS', str(tmp_path / 'vm'))
    suite = load_config(str(root / config)).suite('vm-tests')
    suite.dir.mkdir(parents=True)
    (suite.dir / 'ae_ptw').write_bytes(b'ELF fixture')
    (suite.dir / 'ae_ptw.dump').write_text('disassembly')
    assert [t.id for t in discover(suite)] == ['ae_ptw']


def test_project_dispatches_act4_and_vm_without_core_names(fake, rvw, tmp_path):
    act = tmp_path / 'act4/priv'
    act.mkdir(parents=True)
    (act / 'trap.elf').write_text('status=fail fail_code=9\n')
    (act / 'trap.sig.elf.objdump').write_text('not a program')
    vm = tmp_path / 'vm'
    vm.mkdir()
    (vm / 'page-fault').write_text('status=pass\n')
    project = tmp_path / 'rvw.toml'
    project.write_text(fake.config.read_text() + '''
[suites.act4]
dir = "act4"
glob = "**/*.elf"
strip_suffix = ".elf"
max_cycles = 5000000
timeout_s = 30
[suites.vm-tests]
dir = "vm"
max_cycles = 200000
timeout_s = 30
''')
    out = tmp_path / 'run'
    code, _, data = rvw('--project', project, 'regress', 'run', '--suite',
                        'act4,vm-tests', '--out', out, '--json')
    assert code == 1 and data['counts'] == {'fail': 1, 'pass': 1}
    act_result = load_results(out / 'act4/small')
    assert [(t.id, t.status, t.signature) for t in act_result.tests] == [('priv/trap', 'fail', 'fail:9')]
    assert load_results(out / 'vm-tests/small').tests[0].status == 'pass'
