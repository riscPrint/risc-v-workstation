from pathlib import Path
import pytest
from rvw.cosim.custom import validate_extensions, capture_extensions, load_extensions
from rvw.common.capture import Capture


def test_relative_library_is_captured(tmp_path):
    library = tmp_path/'custom.so'
    library.write_bytes(b'extension fixture')
    capture = Capture(tmp_path/'capture')
    items = capture_extensions([dict(library='custom.so', name='custom')], capture, tmp_path/'platform.json')
    assert Path(items[0]['library']).read_bytes() == library.read_bytes()
    assert Path(items[0]['library']) != library
    assert capture.record()['files'][0]['sha256']


@pytest.mark.parametrize('value', [{}, [dict(name='x')], [dict(name='', library='a')],
                                     [dict(name='x', library='a')]*2])
def test_invalid_declaration(value):
    with pytest.raises(ValueError):
        validate_extensions(value)


def test_declared_libraries_loaded_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr('rvw.cosim.custom.ctypes.CDLL', lambda path, mode: calls.append(path) or path)
    assert load_extensions([dict(name='one', library='a'), dict(name='two', library='b')]) == ['a', 'b']
    assert calls == ['a', 'b']


def test_native_custom_instruction_known_and_negative(tmp_path, tmp_path_factory):
    import ctypes
    import json
    import shutil
    from rvw.common.proc import run_group
    from rvw.cosim.platform import Platform
    from rvw.cosim.checker import check
    from cosim_build import _build
    from model_fixtures import Spike
    from test_state import fixture
    prefix = Path('/opt/homebrew/Cellar/riscv-isa-sim/main')
    if not (prefix/'include/riscv/extension.h').exists() or not shutil.which('c++'):
        pytest.skip('matching native Spike headers and C++ compiler required')
    root = Path(__file__).resolve().parents[3]
    library = tmp_path/'extension.so'
    built = run_group(['nice', '-n', '10', 'c++', '-std=c++17', '-dynamiclib',
        '-I'+str(prefix/'include'), str(root/'Cosim/tests/custom_extension.cc'),
        '-L'+str(prefix/'lib'), '-lriscv', '-o', str(library)], capture=True, timeout=60)
    assert built.returncode == 0, built.stderr
    source = tmp_path/'custom.S'
    source.write_text('.section .text\n.globl _start\n_start: .word 0x8b\n nop\n')
    elf = _build(tmp_path_factory, source)
    platform = Platform.load('boom')
    capture = Capture(tmp_path/'inputs')
    platform.reference_extensions = capture_extensions([dict(name='rvw_example', library=str(library))], capture, tmp_path/'platform.json')
    header, row = fixture()
    header['schema'] = 'rvw.rvfi/1'
    row = {k: v for k, v in row.items() if k not in ('fd_valid', 'fd', 'fd_wdata', 'fflags', 'fcsr')}
    row.update(insn='0x8b', rd=1, rd_wdata='0x7')
    for value, expected in [('0x7', 'match'), ('0x8', 'mismatch')]:
        row['rd_wdata'] = value
        trace = tmp_path/'trace.jsonl'
        trace.write_text('\n'.join(json.dumps(r) for r in [header, row, dict(event='end', cycle=2, status='pass')]))
        model = Spike(platform, elf)
        try:
            result = check(trace, model, platform, sync=())
            assert result['status'] == expected, result
        finally:
            model.close()
