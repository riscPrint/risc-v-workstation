from pathlib import Path

import json
import subprocess
import sys

import pytest

from rvw.wave import ops, vcd

VCD = """$date today $end
$timescale 1ps $end
$scope module TOP $end
$var wire 1 ! clk $end
$scope module Top $end
$var wire 8 " count [7:0] $end
$var wire 1 # valid $end
$var real 64 $ temp $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
b00000000 "
0#
r0.5 $
$end
#5
1!
#10
0!
b00000001 "
#15
1!
1#
#20
0!
b00000010 "
#25
1!
#30
0!
b0000001x "
0#
#40
"""


@pytest.fixture
def wave(tmp_path):
    p = tmp_path / "w.vcd"
    p.write_text(VCD)
    return str(p)


def test_header(wave):
    vs = ops.list_signals(wave)
    names = {v.name: v for v in vs}
    assert set(names) == {"TOP.clk", "TOP.Top.count", "TOP.Top.valid", "TOP.Top.temp"}
    assert names["TOP.Top.count"].width == 8 and names["TOP.Top.count"].range == "[7:0]"


def test_changes(wave):
    rows = ops.changes(wave, r"count")
    assert [(r["time"], r["value"]) for r in rows] == [(0, "0x0"), (10, "0x1"), (20, "0x2"), (30, "b0000001x")]
    rows = ops.changes(wave, r"count", t0=10, t1=20)
    assert [r["time"] for r in rows] == [10, 20]
    assert len(ops.changes(wave, r".", limit=3)) == 3


def test_sample(wave):
    assert ops.sample(wave, r"Top\.", 15) == {"TOP.Top.count": "0x1", "TOP.Top.valid": "1", "TOP.Top.temp": "0.5"}
    assert ops.sample(wave, r"count", 22, radix="dec") == {"TOP.Top.count": "2"}


def test_period_and_end(wave):
    assert ops.detect_period(wave) == 10
    assert vcd.end_time(wave) == 40
    assert ops.parse_time("2c", 10) == 20


@pytest.mark.parametrize("regex", [None, r"count|valid"])
@pytest.mark.parametrize("suffix", [".vcd", ".vcd.gz"])
def test_cut_equivalent(wave, tmp_path, regex, suffix):
    out = str(tmp_path / ("cut" + suffix))
    r = ops.cut(wave, out, 12, 25, regex)
    assert r["signals"] == (4 if regex is None else 2)
    for t in (12, 15, 20, 25):
        want = ops.sample(wave, r"count|valid", t)
        assert ops.sample(out, r"count|valid", t) == want
    # nothing after the window
    assert all(x["time"] <= 25 for x in ops.changes(out, "."))


def test_cut_rebase(wave, tmp_path):
    out = str(tmp_path / "c.vcd")
    ops.cut(wave, out, 20, 30, rebase=True)
    assert ops.sample(out, "count", 0) == {"TOP.Top.count": "0x2"}
    assert ops.sample(out, "count", 10) == {"TOP.Top.count": "b0000001x"}


@pytest.mark.parametrize('t0,t1', [(-1, None), (0, -1), (20, 10)])
@pytest.mark.parametrize('entry', ['api', 'cli', 'mcp'])
def test_invalid_wave_bounds_preserve_output(wave, tmp_path, t0, t1, entry, rvw):
    from rvw.wave import mcp_tools
    out = tmp_path / 'output.vcd'
    out.write_text('keep existing output')
    if entry == 'cli':
        args = ['wave', 'cut', wave, '--from', str(t0), '--out', str(out), '--json']
        if t1 is not None:
            args += ['--to', str(t1)]
        rc, text, _ = rvw(*args)
        assert rc == 2
    else:
        with pytest.raises(vcd.WaveError, match='non-negative|before|greater'):
            if entry == 'api':
                ops.cut(wave, str(out), t0, t1)
            else:
                mcp_tools._cut(wave, str(out), str(t0), None if t1 is None else str(t1))
    assert out.read_text() == 'keep existing output'


@pytest.mark.parametrize('t0,t1', [(-1, None), (0, -1), (20, 10)])
def test_invalid_wave_change_bounds_refuse(wave, t0, t1):
    with pytest.raises(vcd.WaveError, match='non-negative|before|greater'):
        ops.changes_page(wave, '.', t0, t1)


@pytest.mark.parametrize('operation', ['changes', 'changes_page', 'sample', 'sample_raw'])
def test_negative_wave_query_arguments_refuse(wave, operation):
    with pytest.raises(vcd.WaveError, match='non-negative'):
        if operation in ('changes', 'changes_page'):
            getattr(ops, operation)(wave, '.', limit=-1)
        elif operation == 'sample':
            ops.sample(wave, '.', -1)
        else:
            ops.sample_raw(wave, ['TOP.clk'], -1)


@pytest.mark.parametrize('operation', ['changes', 'sample'])
@pytest.mark.parametrize('entry', ['cli', 'mcp'])
def test_negative_wave_query_cli_mcp_parity(wave, rvw, operation, entry):
    from rvw.mcp.registry import Registry

    if entry == 'cli':
        flags = ['--limit', '-1'] if operation == 'changes' else ['--at', '-1']
        rc, output, result = rvw('wave', operation, wave, '.', *flags, '--json')
        assert rc == 2 and 'non-negative' in result['error']
    else:
        registry, problems = Registry.discover({'wave'})
        assert not problems
        try:
            options = {'limit': -1} if operation == 'changes' else {'at': '-1'}
            _, result, error = registry.call_json('wave_' + operation,
                                                  {'wave': wave, 'regex': '.', **options})
            assert error and ('non-negative' in result['error'] or 'minimum' in result['error'])
        finally:
            registry.jobs.shutdown()


@pytest.mark.parametrize('operation,options', [
    ('list', {'regex': '['}),
    ('sample', {'regex': '[', 'at': '0'}),
    ('changes', {'regex': '['}),
    ('cut', {'t0': '0', 'signals': '['}),
    ('info', {'clock': '['}),
    ('sample', {'regex': '.', 'at': '10cc'}),
    ('sample', {'regex': '.', 'at': 'typo'}),
    ('changes', {'regex': '.', 't0': '10cc'}),
    ('changes', {'regex': '.', 't1': 'typo'}),
    ('cut', {'t0': '10cc'}),
    ('cut', {'t0': '0', 't1': 'typo'}),
])
@pytest.mark.parametrize('entry', ['text', 'json', 'mcp'])
def test_invalid_wave_arguments_are_errors(wave, tmp_path, rvw, operation, options, entry):
    from rvw.mcp.registry import Registry

    options = dict(options)
    out = tmp_path / 'keep.vcd'
    out.write_text('keep existing output')
    if operation == 'cut':
        options['out'] = str(out)
    if entry == 'mcp':
        registry, problems = Registry.discover({'wave'})
        assert not problems
        try:
            _, result, error = registry.call_json('wave_' + operation, {'wave': wave, **options})
            assert error
            bad_regex = any(options.get(key) == '[' for key in ('regex', 'signals', 'clock'))
            prefix = 'invalid signal regex:' if bad_regex else 'invalid wave time:'
            assert result['error'].startswith(prefix)
            assert result['diagnostics'][0]['message'] == result['error']
        finally:
            registry.jobs.shutdown()
    else:
        args = ['wave', operation, wave]
        regex = options.pop('regex', None)
        if regex is not None:
            args.append(regex)
        for key, value in options.items():
            args += ['--' + {'t0': 'from', 't1': 'to'}.get(key, key), value]
        if entry == 'json':
            args.append('--json')
        rc, output, result = rvw(*args)
        assert rc == 2
        assert 'rvw wave:' in rvw.stderr and 'Traceback' not in rvw.stderr
        assert result['error'] if entry == 'json' else output == ''
    assert out.read_text() == 'keep existing output'


def test_fst_roundtrip(wave, tmp_path):
    if not vcd.tool("vcd2fst") or not vcd.tool("fst2vcd"):
        pytest.skip("GTKWave tools not available")
    out = str(tmp_path / "c.fst")
    ops.cut(wave, out, 10, 30, r"count")
    assert ops.sample(out, "count", 20) == {"TOP.Top.count": "0x2"}


def test_cli(wave):
    out = subprocess.run([sys.executable, "-m", "rvw.cli", "wave", "sample", wave, "count", "--at", "2c", "--json"],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"time": 20, "values": {"TOP.Top.count": "0x2"}}


def test_changes_default_limit_and_truncated_flag(wave, tmp_path):
    # Review (O): `rvw wave changes` had no default limit and no way to tell a result was cut.
    import json
    import subprocess
    import sys
    assert ops.DEFAULT_CHANGES_LIMIT == 10000
    page = ops.changes_page(wave, ".", limit=3)
    assert len(page["changes"]) == 3 and page["truncated"] is True and page["limit"] == 3
    full = ops.changes_page(wave, ".", limit=0)
    assert full["truncated"] is False and full["changes"] == ops.changes(wave, ".")
    exact = ops.changes_page(wave, ".", limit=len(full["changes"]))
    assert exact["truncated"] is False
    p = subprocess.run([sys.executable, "-m", "rvw", "wave", "changes", wave, ".", "--limit", "2", "--json"],
                       capture_output=True, text=True)
    out = json.loads(p.stdout)
    assert out["truncated"] and len(out["changes"]) == 2
    p = subprocess.run([sys.executable, "-m", "rvw", "wave", "changes", wave, "."], capture_output=True, text=True)
    assert p.returncode == 0 and "truncated" not in p.stderr


def test_cut_refuses_to_overwrite_its_input(wave):
    # Review (S): cutting a wave onto itself destroyed the source.
    from rvw.wave.vcd import WaveError
    before = open(wave).read()
    with pytest.raises(WaveError):
        ops.cut(wave, wave, 12, 25)
    assert open(wave).read() == before


@pytest.mark.parametrize('tail_bytes', [1 << 16, 3 << 16])
@pytest.mark.parametrize('prefix', ['0', '1', 'x', 'z', 'b01 '])
def test_end_time_drops_partial_value_records(tmp_path, tail_bytes, prefix):
    """Review 15: a tail chunk starting at the id #9 is not a timestamp."""
    import gzip
    from rvw.bundle.clock import WaveClock, covers
    header = ('$timescale 1ps $end\n$scope module top $end\n'
              '$var wire 2 #9 value $end\n$var wire 1 ! other $end\n'
              '$upscope $end\n$enddefinitions $end\n')
    suffix = '#9\n' + '0!\n' * ((tail_bytes - 3) // 3)
    suffix += '\n' * (tail_bytes - len(suffix))
    assert len(suffix) == tail_bytes
    text = header + '#5\n' + prefix + suffix
    path = tmp_path / 'partial.vcd'
    path.write_text(text)
    packed = tmp_path / 'partial.vcd.gz'
    with gzip.open(packed, 'wt') as f:
        f.write(text)
    assert vcd.end_time(str(path)) == vcd.end_time(str(packed)) == 5
    assert ops.info(str(path)).end == 5
    clock = WaveClock(1, 1, True, 'fixture')
    run = {'details': {'wave_time_per_cycle': 1, 'wave_time_of_cycle_1': 1}}
    ok, reason = covers(run, path, 9, clock)
    assert not ok and 'before the failure' in reason


@pytest.mark.parametrize('text,expected', [('', None), ('#0', 0), ('#0\n#5', 5),
                                         ('0!\n' * 30000, None),
                                         ('0!\n' * 30000 + '#9\n' + '0!\n' * 21844 + '\n', 9)])
def test_end_time_tail_boundaries(tmp_path, text, expected):
    path = tmp_path / 'boundary.vcd'
    path.write_text(text)
    assert vcd.end_time(str(path)) == expected


@pytest.mark.parametrize('layout', ['indent', 'combined', 'split'])
def test_whitespace_records_and_fst_roundtrip(tmp_path, layout):
    """Review 16: whitespace must not change wave or bundle evidence."""
    assert vcd.tool('vcd2fst') and vcd.tool('fst2vcd'), 'GTKWave tools required'
    text = VCD
    if layout == 'indent':
        text = '\n'.join('  ' + line for line in text.splitlines()) + '\n'
    elif layout == 'combined':
        text = ' \t '.join(text.split()) + '\n'
    else:
        text = '\n\t'.join(text.split()) + '\n'
    path = tmp_path / 'layout.vcd'
    path.write_text(text)
    canonical = tmp_path / 'canonical.vcd'
    canonical.write_text(VCD)
    fst = tmp_path / 'layout.fst'
    back = tmp_path / 'roundtrip.vcd'
    # Exercise the reported indented input through GTKWave itself. For compact or split
    # headers, compare with the round trip of the same records in canonical layout.
    source = path if layout == 'indent' else canonical
    subprocess.run([vcd.tool('vcd2fst'), str(source), str(fst)], check=True)
    with back.open('w') as f:
        subprocess.run([vcd.tool('fst2vcd'), str(fst)], stdout=f, check=True)
    for p in (str(path), str(fst), str(back)):
        assert ops.sample(p, '.', 20) == ops.sample(str(canonical), '.', 20)
        # FST can normalize vector spelling and reorder simultaneous changes.
        rows = lambda name: sorted((r['time'], r['signal'], r['value'])
                                   for r in ops.changes(name, '.'))
        assert rows(p) == rows(str(canonical))
        assert ops.detect_period(p) == 10
        inf = ops.info(p)
        assert (inf.start, inf.end) == (0, 40)
        out = str(tmp_path / (Path(p).name + '.cut.vcd'))
        ops.cut(p, out, 12, 25)
        for t in (12, 15, 20, 25):
            assert ops.sample(out, '.', t) == ops.sample(str(canonical), '.', t)


@pytest.mark.parametrize('body', ['#bad', '#10 #5', 'b02 !', 'b10', 'q1 !',
                                  '$dumpports $end', '$comment unfinished'])
def test_unsupported_vcd_body_refuses(tmp_path, body):
    path = tmp_path / 'bad.vcd'
    path.write_text(VCD.split('#0')[0] + body + '\n')
    with pytest.raises(vcd.WaveError):
        ops.sample(str(path), '.', 100)


def test_fst_converter_failure_cannot_supply_sample(tmp_path, monkeypatch):
    # A converter can write a valid prefix and still fail. Never sample that prefix.
    converter = tmp_path / 'fst2vcd'
    converter.write_text('#!/bin/sh\ncat <<\'VCD\'\n' + VCD + 'VCD\nexit 2\n')
    converter.chmod(0o755)
    monkeypatch.setattr(vcd, 'tool', lambda _: str(converter))
    (tmp_path / 'input.fst').touch()  # The converter fixture still needs a capturable input.
    with pytest.raises(vcd.WaveError, match='fst2vcd failed'):
        ops.sample(str(tmp_path / 'input.fst'), 'count', 20)


@pytest.mark.parametrize('body', ['#0 b1 " #10 b10 #20', '#0 b1 " #10 b10 unknown',
                                  '#0 0unknown'])
def test_undeclared_or_missing_value_identifier_refuses(tmp_path, body):
    path = tmp_path / 'bad-id.vcd'
    path.write_text(VCD.split('#0')[0] + body)
    with pytest.raises(vcd.WaveError, match='identifier'):
        ops.sample(str(path), '.', 100)
    with pytest.raises(vcd.WaveError, match='identifier'):
        vcd.end_time(str(path))


@pytest.mark.parametrize('timestamp,code', [(0, '!'), (5, '#9')])
def test_single_timestamp_fst_queries(tmp_path, rvw, timestamp, code):
    """Review 17: fst2vcd can omit $end after a single timestamp's dumpvars."""
    from rvw.common.proc import run_group
    from rvw.mcp.registry import Registry
    from test_mcp_tools import call
    from rvw.mcp.envelope import envelope
    assert vcd.tool('vcd2fst') and vcd.tool('fst2vcd'), 'GTKWave tools required'
    source = tmp_path / 'static.vcd'
    source.write_text('$timescale 1ps $end\n$scope module TOP $end\n'
                      f'$var wire 1 {code} sig $end\n$upscope $end\n'
                      f'$enddefinitions $end\n#{timestamp}\n1{code}\n')
    fst = tmp_path / 'static.fst'
    assert run_group([vcd.tool('vcd2fst'), str(source), str(fst)], capture=True).returncode == 0
    registry, problems = Registry.discover({'wave'})
    assert not problems
    try:
        for path in (str(source), str(fst)):
            info = ops.info(path)
            assert (info.start, info.end, info.signals, info.period) == (timestamp, timestamp, 1, None)
            assert ops.sample(path, 'sig', timestamp) == {'TOP.sig': '1'}
            assert ops.changes(path, 'sig') == [{'time': timestamp, 'signal': 'TOP.sig', 'value': '1'}]
            for name, opts, args in [('info', {}, []),
                                     ('sample', {'regex': 'sig', 'at': 'end'}, ['sig', '--at', 'end']),
                                     ('changes', {'regex': 'sig'}, ['sig'])]:
                result = call(registry, 'wave_' + name, wave=path, **opts)
                cli = rvw('wave', name, path, *args, '--json')
                assert cli[0] == 0 and result == envelope(cli[2])
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize('body,repairable', [
    ('#5 $dumpvars 1!', True),
    ('#5 $dumpvars b1 !', True),
    ('#5 $dumpvars x!', True),
    ('#5 $dumpall 1!', False),
    ('#5 $dumpon 1!', False),
    ('#5 $dumpoff 1!', False),
    ('#0 #5 $dumpvars 1!', False),
    ('#0 $dumpvars 0! $end #5 $dumpvars 1!', False),
    ('#5 0! $dumpvars 1!', False),
    ('$dumpvars 1!', False),
    ('#5 $dumpvars', False),
    ('#5 $dumpvars b1', False),
    ('#5 $dumpvars 1unknown', False),
    ('#5 $dumpvars #10 1!', False),
    ('#5 $dumpvars $dumpvars 1!', False),
    ('#5 $dumpvars $comment unfinished', False),
])
def test_fst_repairs_only_initial_dumpvars_eof(tmp_path, monkeypatch, body, repairable):
    import shlex
    header = ('$timescale 1ps $end\n$scope module TOP $end\n'
              '$var wire 1 ! sig $end\n$upscope $end\n$enddefinitions $end\n')
    direct = tmp_path / 'truncated.vcd'
    direct.write_text(header + body + '\n')
    with pytest.raises(vcd.WaveError):
        ops.sample(str(direct), 'sig', 100)
    # A successful converter is necessary, but not sufficient, to accept this EOF form.
    converter = tmp_path / 'fst2vcd'
    converter.write_text('#!/bin/sh\ncat ' + shlex.quote(str(direct)) + '\n')
    converter.chmod(0o755)
    monkeypatch.setattr(vcd, 'tool', lambda _: str(converter))
    fst = str(tmp_path / 'static.fst')
    Path(fst).touch()  # Converter output is mocked; capture still checks its raw input.
    if repairable:
        assert ops.sample(fst, 'sig', 100)['TOP.sig'] in ('1', '0x1', 'x')
        assert vcd.end_time(fst) == 5
    else:
        with pytest.raises(vcd.WaveError):
            ops.sample(fst, 'sig', 100)
