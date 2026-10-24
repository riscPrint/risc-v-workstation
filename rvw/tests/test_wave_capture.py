"""C8 waveform races across API, CLI and MCP reads."""
from pathlib import Path
import pytest
from race_injection import race_injector
from rvw.wave import mcp_tools, ops, vcd
from test_wave import VCD


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
@pytest.mark.parametrize('entry', ['mcp', 'cli', 'api'])
def test_wave_end_uses_captured_bytes(tmp_path, race_injector, replace, revert, entry, rvw):
    path = tmp_path / 'input.vcd'
    path.write_text(VCD)
    expected = ops.sample(str(path), 'count', vcd.end_time(str(path)))
    changed = VCD.replace('b0000001x ', 'b00000000 ').replace('#40', '#400')
    # Alter the live wave during the value read, after the end-time read.
    hook = race_injector.file(ops, 'sample', path, changed.encode(), replace=replace, revert=revert)
    if entry == 'mcp':
        result = mcp_tools._sample(str(path), 'count', 'end')['values']
    elif entry == 'cli':
        code, _, report = rvw('wave', 'sample', path, 'count', '--at', 'end', '--json')
        assert code == 0
        result = report['values']
    else:
        # info itself has several read boundaries.
        hook = race_injector.file(vcd, 'end_time', path, changed.encode(), replace=replace, revert=revert)
        result = ops.info(str(path)).end
        expected = 40
    assert hook.fired
    assert result == expected



@pytest.mark.parametrize('suffix', ['.vcd.gz', '.fst'])
@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_encoded_wave_uses_one_raw_capture(tmp_path, race_injector, suffix, replace, revert):
    import gzip
    from rvw.common.proc import run_group
    old = VCD
    new = VCD.replace('b0000001x ', 'b00000000 ').replace('#40', '#400')
    path = tmp_path / ('wave' + suffix)
    if suffix == '.vcd.gz':
        original, replacement = gzip.compress(old.encode()), gzip.compress(new.encode())
    else:
        raw = tmp_path / 'raw.vcd'
        raw.write_text(old)
        assert run_group([vcd.tool('vcd2fst'), str(raw), str(path)], capture=True).returncode == 0
        original = path.read_bytes()
        raw.write_text(new)
        assert run_group([vcd.tool('vcd2fst'), str(raw), str(path)], capture=True).returncode == 0
        replacement = path.read_bytes()
    path.write_bytes(original)
    expected = ops.sample(str(path), 'count', 40)
    hook = race_injector.file(ops, 'sample', path, replacement, replace=replace, revert=revert)
    result = mcp_tools._sample(str(path), 'count', 'end')
    assert hook.fired and result == {'time': 40, 'values': expected}


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_changed_converter_refuses_before_cli_output(tmp_path, monkeypatch, race_injector, replace, revert, rvw):
    from rvw.common.proc import run_group
    # A private converter avoids changing any installed tool.
    converter = tmp_path / 'fst2vcd'
    import shlex
    real = vcd.tool('fst2vcd')
    converter.write_text('#!/bin/sh\nexec ' + shlex.quote(real) + ' "$@"\n')
    converter.chmod(0o755)
    raw = tmp_path / 'raw.vcd'
    raw.write_text(VCD)
    fst = tmp_path / 'input.fst'
    assert run_group([vcd.tool('vcd2fst'), str(raw), str(fst)], capture=True).returncode == 0
    monkeypatch.setenv('PATH', str(tmp_path) + ':' + __import__('os').environ['PATH'])
    hook = race_injector.file(vcd, 'run_group', converter,
                             converter.read_bytes() + b'# changed during conversion\n',
                             replace=replace, revert=revert)
    code, stdout, data = rvw('wave', 'sample', fst, 'count', '--at', 'end', '--json')
    assert hook.fired and code != 0 and stdout == '' and data is None
    assert 'input_not_captured:tool:' in rvw.stderr
