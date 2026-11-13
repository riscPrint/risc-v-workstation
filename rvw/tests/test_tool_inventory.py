import importlib.util
import subprocess
from pathlib import Path
import pytest
from rvw.doctor import inventory

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_profiles_and_flags():
    data = inventory.load()
    assert set(data['profiles']) == {'minimal', 'verification', 'formal', 'arch', 'all'}
    assert inventory.flags('minimal') == []
    assert '--with-ric3' in inventory.flags('all')
    for tool in data['tools']:
        assert tool['flag'] in data['profiles']['all'] or tool['flag'] in ('sail', 'ide')
        assert tool['install']['linux_status'] == 'untested'
        assert tool['pin']
    with pytest.raises(ValueError):
        inventory.flags('wrong')


def test_profile_expansion_preserves_paths():
    p = subprocess.run(['python3', str(ROOT / 'scripts/tool-inventory.py'), '--expand', '--prefix', '/tmp/a b', '--profile', 'verification'], capture_output=True, text=True)
    assert p.returncode == 0
    assert p.stdout.splitlines()[:2] == ['--prefix', '/tmp/a b']
    assert '--with-cosim' in p.stdout


def test_presence_is_not_qualification(monkeypatch):
    monkeypatch.setattr(inventory.shutil, 'which', lambda p: None)
    monkeypatch.setattr(importlib.util, 'find_spec', lambda p: None)
    monkeypatch.setattr(Path, 'is_file', lambda p: False)
    records = inventory.report()
    assert all(r['status'] == 'missing' for r in records)
    assert all('runtime NOT RUN' in r['qualification'] for r in records)
    assert all(r['install_flag'].startswith('--with-') for r in records)


def test_generated_version_table_matches_inventory():
    done = subprocess.run(['python3', str(ROOT / 'scripts/generate-tool-docs.py'), '--check'], capture_output=True, text=True)
    assert done.returncode == 0


@pytest.mark.parametrize('manager,expected', [('apt','openocd'),('dnf','openocd'),('brew','open-ocd')])
def test_package_recipe_plan(manager, expected):
    done=subprocess.run(['python3',str(ROOT/'scripts/tool-inventory.py'),'--packages',manager,'--extra','openocd'],capture_output=True,text=True)
    assert done.returncode==0
    assert done.stdout.splitlines()==[expected]


def test_linux_plan_is_explicitly_untested():
    done=subprocess.run(['python3',str(ROOT/'scripts/tool-inventory.py'),'--linux-plan','dnf','--extra','ghdl','pono'],capture_output=True,text=True)
    assert done.returncode==0
    assert 'Linux untested' in done.stdout and 'stanford-centaur/pono' in done.stdout


def test_python_extras_share_one_locked_sync(tmp_path):
    done=subprocess.run(['python3',str(ROOT/'scripts/tool-inventory.py'),'--home',str(tmp_path),'--dry-run','--extra','cocotb','pyuvm'],capture_output=True,text=True)
    assert done.returncode==0
    assert done.stdout.count('uv sync')==1
    assert '--extra cocotb' in done.stdout and '--extra pyuvm' in done.stdout
    assert str(tmp_path/'rvw') in done.stdout


def test_plugin_probe_does_not_use_yosys_config_as_plugin(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_HOME',str(tmp_path))
    monkeypatch.delenv('RVW_SLANG', raising=False)
    monkeypatch.setattr(inventory.shutil,'which',lambda p: '/bin/yosys-config')
    row=next(r for r in inventory.report() if r['name']=='yosys-slang')
    assert row['status']=='missing'
    plugin=tmp_path/'slang.so';plugin.write_bytes(b'fixture')
    monkeypatch.setenv('RVW_SLANG',str(plugin))
    row=next(r for r in inventory.report() if r['name']=='yosys-slang')
    assert row['paths']['slang.so']==str(plugin)
    assert row['qualification']=='presence only; runtime NOT RUN'


def test_explicit_invalid_selector_cannot_fall_back(tmp_path,monkeypatch):
    executable=tmp_path/'tool';executable.write_text('#!/bin/sh\nexit 0\n');executable.chmod(0o755)
    monkeypatch.setenv('RVW_GEM5',str(tmp_path/'missing'))
    row=next(t for t in inventory.load()['tools'] if t['name']=='gem5')
    assert inventory.probe_path(row['probes'][0]) is None


def test_managed_circt_prefix_is_detected(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_CIRCT',str(tmp_path))
    for name in ('arcilator','circt-verilog','llc'):
        path=tmp_path/'bin'/name;path.parent.mkdir(exist_ok=True);path.write_text('#!/bin/sh\n');path.chmod(0o755)
    row=next(r for r in inventory.report() if r['name']=='CIRCT/arcilator')
    assert row['status']=='installed'
    assert all(str(tmp_path) in p for p in row['paths'].values())


def test_ghdl_needs_plugin_file_not_just_executable(tmp_path,monkeypatch):
    monkeypatch.setenv('RVW_GHDL_PLUGIN',str(tmp_path/'missing.so'))
    row=next(r for r in inventory.report() if r['name']=='GHDL')
    assert row['status']=='missing'
    assert row['paths']['ghdl.so'] is None


def test_arcilator_check_without_venv_does_not_use_unbound_python(tmp_path):
    import os
    env=dict(os.environ);env.pop('RVW_PYTHON',None)
    done=subprocess.run(['bash',str(ROOT/'scripts/install.sh'),'--with-arcilator','--check','--prefix',str(tmp_path/'absent')],env=env,capture_output=True,text=True)
    assert done.returncode==1
    assert 'MISSING rvw venv' in done.stdout
    assert 'unbound variable' not in done.stderr
