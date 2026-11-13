"""Random campaigns need complete independent evidence before coverage credit."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.regress import random_stream as random


def fixture(tmp_path, monkeypatch):
    elf = tmp_path/'program.elf'
    elf.write_bytes(b'\x7fELFfixture')
    trace = tmp_path/'rvfi.jsonl'
    trace.write_text('{}\n')
    (tmp_path/'result.json').write_text('{}')
    run = SimpleNamespace(core='fixture', elf_sha256=random.digest(elf), why_inconclusive=None,
                          status='pass', instret=2, path=tmp_path, artifact=lambda _: trace)
    monkeypatch.setattr(random, 'load_run', lambda _: run)
    monkeypatch.setattr(random, 'functional', lambda *a, **k: {'retired': 2})
    comparison = dict(status='match', trace_complete=True, end_status='pass', instructions=2)
    monkeypatch.setattr(random, 'cosim', lambda *a, **k: comparison)
    return elf, run, comparison


@pytest.mark.parametrize('changes,status', [({}, 'pass'), ({'trace_complete':False}, 'cosim_error'),
    ({'end_status':'rvfi_error'}, 'cosim_error'), ({'instructions':1}, 'cosim_error'),
    ({'instructions':0}, 'cosim_error'), ({'status':'mismatch'}, 'mismatch'),
    ({'status':'error'}, 'cosim_error'), ({'synchronized':1}, 'cosim_error')])
def test_credit_requires_complete_spike_match(tmp_path, monkeypatch, changes, status):
    elf, run, comparison = fixture(tmp_path, monkeypatch)
    comparison.update(changes)
    result = random.verify(elf, tmp_path, tmp_path/'platform.json')
    assert result['status'] == status
    assert ('coverage' in result) == (status == 'pass')


@pytest.mark.parametrize('status,reason,expected', [('fail', None, 'core_failure'),
    ('error', 'monitor failed', 'adapter_error')])
def test_failed_c1_earns_no_credit(tmp_path, monkeypatch, status, reason, expected):
    elf, run, _ = fixture(tmp_path, monkeypatch)
    run.status, run.why_inconclusive = status, reason
    monkeypatch.setattr(random, 'cosim', lambda *a, **k: pytest.fail('must not compare failed C1'))
    assert random.verify(elf, tmp_path, 'platform.json')['status'] == expected


def test_missing_trace_and_wrong_elf(tmp_path, monkeypatch):
    elf, run, _ = fixture(tmp_path, monkeypatch)
    run.artifact = lambda _: None
    assert random.verify(elf, tmp_path, 'platform.json')['status'] == 'trace_error'
    elf.write_bytes(b'changed')
    assert random.verify(elf, tmp_path, 'platform.json')['status'] == 'adapter_error'


@pytest.mark.parametrize('stage', ['generator', 'compile', 'adapter', 'success'])
def test_campaign_stages_and_seed_replay(tmp_path, monkeypatch, stage):
    settings = tmp_path/'random.toml'
    settings.write_text('''checkout = "/external/riscv-dv"
python = "/external/venv/bin/python"
target = "rv32imc"
isa = "rv32im_zicsr"
abi = "ilp32"
linker = "link.ld"
runtime = "runtime"
platform = "platform.json"
compiler = "riscv64-unknown-elf-gcc"
''')
    (tmp_path/'link.ld').write_text('fixture')
    (tmp_path/'runtime').mkdir()
    (tmp_path/'runtime/user_init.s').write_text('li x1,0')
    (tmp_path/'platform.json').write_text('{}')
    core = SimpleNamespace(default_config='test', configs=['test'], name='fixture')
    monkeypatch.setattr(random, 'load_config', lambda *a, **k: core)
    monkeypatch.setattr(random, 'source_for', lambda *a: None)
    def command(argv, **kw):
        generation = '--checkout' in argv
        if generation and stage != 'generator':
            directory = Path(argv[argv.index('--out')+1])
            directory.mkdir()
            assembly = directory/'program_0.S'
            assembly.write_text('addi x1,x0,1\n')
            (directory/'generation.json').write_text(json.dumps(dict(status='generated',
                seed=int(argv[argv.index('--seed')+1]), generator_revision=random.REVISION,
                source_sha256=random.digest(assembly))))
        elif not generation and stage != 'compile':
            Path(argv[-1]).write_bytes(b'\x7fELFfixture')
        fail = (generation and stage == 'generator') or (not generation and stage == 'compile')
        return SimpleNamespace(returncode=int(fail), timed_out=False)
    monkeypatch.setattr(random, 'run_group', command)
    plans = []
    def run_plan(core, plan, out, source, opts):
        plans.append((plan, opts))
        if stage == 'adapter':
            raise ValueError('adapter failed')
    monkeypatch.setattr(random, 'run_plan', run_plan)
    monkeypatch.setattr(random, 'verify', lambda *a: dict(status='pass', coverage={'retired':2}))
    result = random.execute_json(tmp_path/'out', settings, seeds=2, seed_base=48)
    assert [a['seed'] for a in result['attempts']] == [48, 49]
    assert result['status'] == ('pass' if stage == 'success' else 'inconclusive')
    assert all(a['status'] == ('pass' if stage == 'success' else stage+'_error') for a in result['attempts'])
    assert result['counts'] == {('pass' if stage == 'success' else stage+'_error'): 2}
    assert json.loads((tmp_path/'out/campaign.json').read_text()) == result
    if stage == 'success':
        assert [o.seed_base for _, o in plans] == [48,49]
        assert all(o.rvfi_trace and not o.use_cache for _, o in plans)
    with pytest.raises(FileExistsError):
        random.execute_json(tmp_path/'out', settings)


def test_project_selects_random_settings(tmp_path, monkeypatch):
    from rvw.common.project import parse_project, load_project
    project_file = tmp_path/'rvw.toml'
    project_file.write_text('[core]\nname="fixture"\n[stimulus]\nrandom_settings="random.toml"\n')
    selected = load_project(project_file)
    assert selected.get('stimulus', 'random_settings') == tmp_path/'random.toml'
    with pytest.raises(ValueError, match='non-empty path'):
        parse_project({'core': {'name':'fixture'}, 'stimulus': {'random_settings': []}}, project_file, {})
    with pytest.raises(FileNotFoundError):
        random.execute_json(tmp_path/'out', project=project_file)


def test_installer_refuses_repository_path_and_dry_run_is_read_only(tmp_path, monkeypatch):
    import subprocess
    import sys
    script = random.ROOT/'scripts/install-riscv-dv.py'
    monkeypatch.setenv('RVW_RISCV_DV', str(random.ROOT/'third-party'))
    result = subprocess.run([sys.executable, str(script), '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 2 and 'outside the repository' in result.stderr
    external = tmp_path/'external'
    monkeypatch.setenv('RVW_RISCV_DV', str(external))
    result = subprocess.run([sys.executable, str(script), '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 0 and random.REVISION in result.stdout
    assert not external.exists()


def test_reference_uses_c1_core_outside_project_directory(tmp_path,monkeypatch):
    elf,run,comparison=fixture(tmp_path,monkeypatch)
    seen=[]
    def compare(*args,**kwargs):
        assert kwargs['strict'] is True
        seen.append(kwargs['core']);return comparison
    monkeypatch.setattr(random,'cosim',compare)
    assert random.verify(elf,tmp_path,'platform')['status']=='pass'
    assert seen==['fixture']


@pytest.fixture
def tmp_path(external_tmp_path):
    return external_tmp_path
