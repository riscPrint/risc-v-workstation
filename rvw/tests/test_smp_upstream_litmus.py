"""The upstream profile refuses instruction rewriting and missing semantics."""
import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
SOURCE = Path(__file__).resolve().parents[2]/'examples/smp/rvw/litmus_catalog.py'
spec = importlib.util.spec_from_file_location('smp_upstream', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def text(instruction='lw x7,0(x6)', initial='0:x6=x; 1:x6=y;', final='0:x7=0 /\\ 1:x7=0'):
    return f'RISCV sample\n{{{initial}}}\nP0 | P1;\n{instruction} | lw x7,0(x6);\nexists ({final})\n'


def test_parse_preserves_instructions_and_shared_addresses():
    parsed = module.parse_text(text('amoadd.d.aqrl x7,x8,0(x6)'))
    assert parsed['harts'] == 2
    assert parsed['registers'] == [{6: 0x81000000}, {6: 0x81000040}]
    assert parsed['instructions'][0] == ['amoadd.d.aqrl x7,x8,0(x6)']
    assert parsed['projection'] == ['0:x7', '1:x7']


@pytest.mark.parametrize('instruction', ['sw.rl x5,0(x6)', 'lw.aq x7,0(x6)', 'j loop',
                                       'csrr x5,mhartid', 'lw x30,0(x6)'])
def test_unknown_or_reserved_instruction_is_not_rewritten(instruction):
    with pytest.raises(ValueError, match='unsupported instruction'):
        module.parse_text(text(instruction))


def test_memory_initialization_and_final_sampling_limits():
    with pytest.raises(ValueError, match='zero memory'):
        module.parse_text(text(initial='x=1; 0:x6=x; 1:x6=y;'))
    with pytest.raises(ValueError, match='memory final'):
        module.parse_text(text(final='x=1 /\\ 1:x7=0'))


def test_empty_cells_and_comments():
    parsed = module.parse_text(text('(* wait *)'))
    assert parsed['instructions'][0] == []
    parsed = module.parse_text(text('lr.w x7,0(x6)'))
    assert parsed['instructions'][0] == ['lr.w x7,0(x6)']


def test_build_initializes_unspecified_registers_and_preserves_projection(tmp_path, monkeypatch):
    import runpy
    captured = {}
    def build(out, **kwargs):
        captured.update(kwargs)
        Path(out).mkdir()
        return Path(out)/'hart-images.json'
    monkeypatch.setattr(runpy, 'run_path', lambda _: {'build': build})
    source = tmp_path/'case.litmus'
    source.write_text(text())
    module.build(source, tmp_path/'out')
    asm = captured['sources'][0]
    assert 'li x1, 0' in asm and 'li x29, 0' in asm
    assert asm.index('li x6, 0') < asm.index('li x6, 2164260864')
    assert asm.index('lw x7,0(x6)') < asm.index('la x30, tohost')


def test_catalog_checks_revision_and_every_source_byte(tmp_path, monkeypatch):
    import subprocess
    root = tmp_path/'source'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    git('init', '-q')
    folder = root/'tests/non-mixed-size'
    folder.mkdir(parents=True)
    source = folder/'sample.litmus'
    source.write_text(text())
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.org', 'commit', '-qm', 'fixture')
    revision = git('rev-parse', 'HEAD')
    monkeypatch.setattr(module, 'PIN', revision)
    rows = module.catalog(root)
    assert len(rows) == 1 and rows[0]['status'] == 'applicable'
    source.write_text(text('addi x7,x7,1'))
    with pytest.raises(ValueError, match='source bytes'):
        module.catalog(root)
    monkeypatch.setattr(module, 'PIN', '0'*40)
    with pytest.raises(ValueError, match='revision'):
        module.catalog(root)


def test_parser_rejects_duplicate_initial_register_and_final_reserved_register():
    with pytest.raises(ValueError, match='initial register'):
        module.parse_text(text(initial='0:x6=x; 0:x6=y; 1:x6=y;'))
    with pytest.raises(ValueError, match='final register'):
        module.parse_text(text(final='0:x30=0'))
