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
