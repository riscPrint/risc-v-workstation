"""Project selections must bind the requested inputs and fail closed."""
import os
from pathlib import Path
import pytest
from rvw.common.project import find_project, load_project
from rvw.regress.config import load_config


def project(fake):
    path = fake.root / 'rvw.toml'
    path.write_text(fake.config.read_text())
    return path


def test_nearest_and_environment(fake, monkeypatch):
    outer = project(fake)
    inner = fake.root / 'nested'
    inner.mkdir()
    (inner / 'rvw.toml').write_text(outer.read_text().replace('name = "fake"', 'name = "inner"'))
    leaf = inner / 'src'
    leaf.mkdir()
    monkeypatch.chdir(leaf)
    assert find_project() == inner / 'rvw.toml'
    monkeypatch.setenv('RVW_PROJECT', str(outer))
    assert load_config().name == 'fake'
    assert load_config(project=inner).name == 'inner'
    assert load_config('boom').name == 'boom'


@pytest.mark.parametrize('index', [0, 1, 3])
def test_cli_project_anywhere(fake, rvw, index):
    path = project(fake)
    args = ['regress', 'list', '--json']
    args[index:index] = ['--project', str(path)]
    code, _, data = rvw(*args)
    assert code == 0 and data['core'] == 'fake'


def test_cli_discovery(fake, rvw, monkeypatch):
    path = project(fake)
    nested = fake.root / 'nested'
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert rvw('regress', 'list', '--json')[2]['core'] == 'fake'
    monkeypatch.chdir('/tmp')
    monkeypatch.setenv('RVW_PROJECT', str(path))
    assert rvw('regress', 'list', '--json')[2]['core'] == 'fake'


def test_defaults_paths_capture(tmp_path, monkeypatch):
    monkeypatch.setenv('PROJECT_PLATFORM', 'config/platform.json')
    path = tmp_path / 'custom.toml'
    path.write_text('''[project]
schema = "rvw.project/1"
root = "src"
[core]
name = "small-core"
adapter = "./scripts/run"
[cosim]
platform = "${PROJECT_PLATFORM}"
[checks]
waivers = "waivers.txt"
[query]
build = ["./scripts/build-db", "./settings"]
db = "out/core.db"
[formal]
verilog = ["out/core.v"]
top = "Core"
''')
    selected = load_project(path)
    assert selected.root == tmp_path / 'src'
    assert selected.get('query', 'db') == tmp_path / 'out/core.db'
    assert selected.get('query', 'build') == [str(tmp_path / 'scripts/build-db'), str(tmp_path / 'settings')]
    core = load_config(project=path)
    assert core.source_repo == selected.root
    assert core.adapter == [str(tmp_path / 'scripts/run')]
    assert tmp_path / 'config/platform.json' in core.cache_paths
    assert core.capture['files'][0]['sha256'] == selected.capture['files'][0]['sha256']


@pytest.mark.parametrize('bad', ['[project]\nschema="rvw.project/999"', '[query]\nbuid=[]', '[cosim]\nplatform=3'])
def test_invalid_never_falls_back(tmp_path, rvw, monkeypatch, bad):
    (tmp_path / 'rvw.toml').write_text('[core]\nname="bad"\nadapter="false"\n' + bad)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('RVW_CORE', 'boom')
    assert rvw('regress', 'list', '--json')[0] == 2
    assert load_config('boom').name == 'boom'


def test_missing_and_ambiguous(fake, rvw, monkeypatch):
    monkeypatch.setenv('RVW_PROJECT', str(fake.root / 'missing.toml'))
    assert rvw('regress', 'list')[0] == 2
    assert rvw('regress', 'list', '--project', project(fake), '--core', 'boom')[0] == 2


def test_mcp_project_and_discovery(fake, monkeypatch):
    from rvw.mcp.registry import Registry
    path = project(fake)
    registry, problems = Registry.discover({'regress'})
    assert not problems
    before = dict(os.environ)
    _, data, error = registry.call_json('regress_list', {'project': str(path)})
    assert not error and data['core'] == 'fake'
    assert dict(os.environ) == before
    monkeypatch.chdir(path.parent)
    assert registry.call_json('regress_list', {})[1]['core'] == 'fake'


def test_gate_declared_source(fake, rvw):
    path = project(fake)
    base = fake.commit(msg='base project')
    candidate = fake.commit(msg='candidate project')
    code, _, data = rvw('regress', 'gate', '--project', path, '--base-rev', base,
                        '--cand-rev', candidate, '--filter', '^rv64ui-p-add$', '--json')
    assert code == 0 and data['verdict'] == 'accept'


def test_query_db_cli_mcp(fake, gcd_db, rvw):
    from rvw.mcp.registry import Registry
    path = project(fake)
    path.write_text(path.read_text() + f'\n[query]\ndb = "{gcd_db}"\n')
    code, _, data = rvw('query', 'info', '--project', path, '--json')
    assert code == 0 and data['meta']['toplevel']
    registry, problems = Registry.discover({'query'})
    assert not problems
    _, data, error = registry.call_json('query_info', {'project': str(path)})
    assert not error and data['meta']['toplevel']


def test_cosim_missing_platform(fake):
    from argparse import Namespace
    from rvw.cosim.inputs import Inputs
    with pytest.raises(ValueError, match='missing cosim.platform'):
        Inputs(Namespace(project=project(fake), core=None, platform=None), fake.root / 'capture')


def test_formal_defaults(fake, rvw, monkeypatch):
    from rvw.formal import flows
    path = project(fake)
    path.write_text(path.read_text() + '\n[formal]\nverilog=["out/core.v"]\ntop="Core"\nclock="clock"\n')
    def flow(args):
        assert args.verilog == [fake.root / 'out/core.v']
        assert args.top == 'Core' and args.clock == 'clock'
        assert args._project_capture['files']
        return 0
    monkeypatch.setattr(flows, 'bmc', flow)
    assert rvw('formal', 'bmc', '--project', path, '--out', fake.root / 'proof')[0] == 0


def test_build_cannot_return_stale_database(fake, gcd_db, monkeypatch):
    from rvw.query.project import build_database
    from rvw.query.db import QueryError
    path = project(fake)
    out = fake.root / 'old.db'
    out.write_bytes(gcd_db.read_bytes())
    path.write_text(path.read_text() + f'\n[query]\nbuild=["/usr/bin/true"]\ndb="{out}"\n')
    with pytest.raises(QueryError):
        build_database(path)
    assert not out.exists()


def test_broken_nearest_project_never_selects_parent(fake, monkeypatch, rvw):
    project(fake)
    nested = fake.root / 'broken-project'
    nested.mkdir()
    (nested / 'rvw.toml').symlink_to(nested / 'missing.toml')
    monkeypatch.chdir(nested)
    assert rvw('regress', 'list', '--json')[0] == 2
    assert 'not a regular file' in rvw.stderr


def test_environment_custom_filename_is_project(tmp_path, monkeypatch):
    path = tmp_path / 'custom.toml'
    path.write_text('[core]\nname="custom"\nadapter="./run.sh"\n')
    monkeypatch.setenv('RVW_PROJECT', str(path))
    assert load_config().source_repo == tmp_path


def test_mcp_startup_project_reaches_calls(fake, monkeypatch, rvw):
    from rvw.mcp.registry import Registry
    path = project(fake)
    before = dict(os.environ)
    original = Registry.discover.__func__
    def discover(cls, only=None, **options):
        registry, problems = original(cls, only, **options)
        _, data, error = registry.call_json('regress_list', {})
        assert not error and data['core'] == 'fake'
        assert registry.call_json('regress_list', {'core': 'boom'})[1]['core'] == 'boom'
        return registry, problems
    monkeypatch.setattr(Registry, 'discover', classmethod(discover))
    assert rvw('mcp', '--project', path, '--only', 'regress', '--list', '--json')[0] == 0
    assert dict(os.environ) == before
    assert rvw('mcp', '--project', fake.root / 'missing', '--list')[0] == 2


def test_debug_selected_project_records_config(fake):
    from rvw.runs.inputs import DebugInputs
    path = project(fake)
    debug = fake.root / 'debug.toml'
    debug.write_text('[core]\nsource_env="FAKE_SRC"\n')
    path.write_text(path.read_text() + '\n[debug]\nconfig="debug.toml"\n')
    inputs = DebugInputs()
    cfg, selected = inputs.config('fake', project=path)
    assert cfg['core']['source_env'] == 'FAKE_SRC' and selected == debug
    assert {row['resolved'] for row in inputs.record()['files']} >= {str(path), str(debug)}


@pytest.mark.parametrize('package,constructor,arguments', [
    ('reduce', 'Reducer', []), ('bisect', 'Bisector', ['--good', 'HEAD']),
])
def test_debug_cli_project_reaches_shared_options(fake, monkeypatch, rvw, package, constructor, arguments):
    import importlib
    cli = importlib.import_module(f'rvw.{package}.cli')
    path = project(fake)
    def start(run_dir, options):
        assert options.project == str(path)
        raise ValueError('selected project reached shared options')
    monkeypatch.setattr(cli, constructor, start)
    assert rvw(package, 'unused-run', '--project', path, *arguments)[0] == 2
    assert 'selected project reached shared options' in rvw.stderr


def test_project_history_scopes_core_cli_and_mcp(fake, monkeypatch, rvw):
    from rvw.regress import cli
    from rvw.mcp.registry import Registry
    path = project(fake)
    monkeypatch.setattr(cli, 'read_index', lambda: [
        {'run_id': 'ours', 'core': 'fake', 'path': str(fake.root)},
        {'run_id': 'other', 'core': 'other', 'path': str(fake.root)},
    ])
    code, _, data = rvw('regress', 'history', '--project', path, '--json')
    assert code == 0 and [row['run_id'] for row in data['runs']] == ['ours']
    registry, problems = Registry.discover({'regress'})
    _, data, error = registry.call_json('regress_history', {'project': str(path)})
    assert not problems and not error and [row['run_id'] for row in data['runs']] == ['ours']


def test_riscv_instruction_model_paths(tmp_path,monkeypatch):
    monkeypatch.setenv('MODELS','generated')
    project=tmp_path/'rvw.toml'
    project.write_text('[core]\nname="formal"\n[riscv_formal.instruction_models]\nadd="${MODELS}/insn_add.v"\n')
    selected=load_project(project)
    assert selected.sections['riscv_formal']['instruction_models']['add']==tmp_path/'generated/insn_add.v'


def test_managed_dependency_omissions_parse_without_resolution(tmp_path, monkeypatch):
    from rvw.common.project import parse_project
    def forbidden(*args, **kwargs):
        pytest.fail('project parsing must not resolve dependencies')
    monkeypatch.setattr('rvw.common.dependencies.resolve', forbidden)
    monkeypatch.setattr('rvw.regress.source.ensure_pinned_source', forbidden)
    parsed = parse_project({'core': {'name': 'example'},
                            'riscv_formal': {'wrapper': 'wrapper.sv'},
                            'arch': {'description': 'description.json', 'benchmarks': 'out'}},
                           tmp_path / 'rvw.toml', {})
    assert 'root' not in parsed.sections['riscv_formal']
    assert parsed.get('arch', 'sources') is None
    assert parsed.get('arch', 'benchmarks') == tmp_path / 'out'
