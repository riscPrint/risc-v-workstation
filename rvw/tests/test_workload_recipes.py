import json
from rvw.workloads import core
from rvw.workloads.mcp_tools import execute_json, mcp_tools
from rvw.cli import main


def test_riscv_recipe_selection(capsys):
    assert main(['workloads', 'list', '--recipe', 'riscv-tests']) == 0
    data = json.loads(capsys.readouterr().out)
    assert {'median', 'dhrystone', 'spmv'} <= {w['id'] for w in data['workloads']}
    assert len(data['revision']) == 40
    assert len(data['dependencies']['env']) == 40
    assert data['runtime_files']
    assert execute_json('list', recipe='riscv-tests') == data
    assert {t.name for t in mcp_tools()} == {'workloads_list', 'workloads_build', 'workloads_verify'}


def test_open_recipe_pins_and_checkers():
    for name, workload in [('coremark', 'coremark-smoke'), ('zstd', 'zstd-roundtrip')]:
        data = core.load(core.recipe(name))
        assert len(data['revision']) == 40
        assert data['workloads'][0]['id'] == workload
        assert data['workloads'][0]['stdout_sha256'] == core.EMPTY
        assert data['workloads'][0]['expected']


def test_capture_dependency_revision(tmp_path):
    import subprocess
    source = tmp_path / 'source'
    source.mkdir()
    subprocess.run(['git', 'init', '-q', str(source)], check=True)
    subprocess.run(['git', '-C', str(source), 'config', 'user.name', 'Test'], check=True)
    subprocess.run(['git', '-C', str(source), 'config', 'user.email', 'test@example.com'], check=True)
    (source / 'encoding.h').write_text('pinned header')
    subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(source), 'commit', '-qm', 'fixture'], check=True)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    (source / 'encoding.h').write_text('dirty header')
    destination = tmp_path / 'captured'
    core.archive_source(source, revision, destination)
    assert (destination / 'encoding.h').read_text() == 'pinned header'
