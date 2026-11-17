from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.regress import isa_build

pytestmark = pytest.mark.fast


@pytest.fixture
def build_env(tmp_path, monkeypatch):
    src = tmp_path / 'source'
    (src / 'env/p').mkdir(parents=True)
    (src / 'env/p/riscv_test.h').write_text('fixture')
    compiler = tmp_path / 'gcc'
    compiler.write_bytes(b'compiler')
    monkeypatch.setattr(isa_build.shutil, 'which', lambda _: str(compiler))
    monkeypatch.setattr(isa_build, 'describe', lambda _: SimpleNamespace(rev='a'*40, dirty=False, reusable=True, to_dict=lambda: {'core_rev_full': 'a'*40}))
    return src, tmp_path / 'out'


def test_success_requires_all_selected_elfs(build_env, monkeypatch):
    src, out = build_env
    def run(command, cwd, **kw):
        (cwd / 'rv64ui-p-add').write_bytes(b'\x7fELFfixture')
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr(isa_build, 'run_group', run)
    result = isa_build.build(out, source=src, targets='rv64ui-p-add,rv64ui-v-add')
    assert result['status'] == 'error'
    assert (out / 'manifest.json').is_file()


def test_failed_process_cannot_pass_with_elf(build_env, monkeypatch):
    src, out = build_env
    def run(command, cwd, **kw):
        (cwd / 'rv64ui-p-add').write_bytes(b'\x7fELFfixture')
        return SimpleNamespace(returncode=1, timed_out=False)
    monkeypatch.setattr(isa_build, 'run_group', run)
    assert isa_build.build(out, source=src, targets='rv64ui-p-add')['status'] == 'error'


def test_build_refuses_existing_output(build_env):
    src, out = build_env
    out.mkdir()
    with pytest.raises(FileExistsError):
        isa_build.build(out, source=src, targets='rv64ui-p-add')


def test_explicit_elf_directory(build_env, monkeypatch, tmp_path):
    src, out = build_env
    custom = tmp_path / 'custom'
    def run(command, cwd, **kw):
        assert cwd == custom
        (cwd / 'rv64ui-p-add').write_bytes(b'\x7fELFfixture')
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr(isa_build, 'run_group', run)
    result = isa_build.build(out, source=src, targets='rv64ui-p-add', elf_dir=custom)
    assert result['status'] == 'built'
    assert (out / 'manifest.json').is_file()
