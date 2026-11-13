"""Review 18: preserve unpacked array element names from real simulators."""
import io
import os
from pathlib import Path

import pytest

from rvw.bundle import snapshot
from rvw.common.proc import run_group
from rvw.mcp.registry import Registry
from rvw.wave import ops, vcd


@pytest.mark.parametrize('name,range_token', [
    (r'\a[0]', ''), (r'\a[1]', ''), (r'\words[0]', '[3:0]'),
    (r'\literal[7:0]', ''), ('a[0]', ''), ('words[1]', '[3:0]'),
])
def test_range_must_be_a_separate_token(name, range_token):
    f = io.StringIO(f'$var wire 4 ! {name} {range_token} $end\n$enddefinitions $end\n')
    var = vcd.read_header(f).vars[0]
    assert (var.name, var.range) == (name, range_token)


@pytest.fixture(scope='module', params=[('icarus', 'vcd'), ('icarus', 'fst'), ('verilator', 'vcd'), ('verilator', 'fst')],
                ids=lambda p: '-'.join(p))
def simulator_wave(request, tmp_path_factory):
    simulator, fmt = request.param
    root = tmp_path_factory.mktemp(f'array-{simulator}-{fmt}')
    wave = root / f'arrays.{fmt}'
    source = root / 'arrays.sv'
    source.write_text(f'''module arrays;
reg a [0:1];
reg [3:0] words [0:1];
initial begin
  $dumpfile("{wave}");
  $dumpvars(0, arrays.a[0], arrays.a[1], arrays.words[0], arrays.words[1]);
  a[0]=0; a[1]=1; words[0]=2; words[1]=5;
  #5 a[0]=1; a[1]=0; words[0]=9; words[1]=10;
  #5 $finish;
end
endmodule
''')
    def run(args):
        env = dict(os.environ)
        env['PATH'] = str(Path(vcd.tool('iverilog')).parent) + os.pathsep + env['PATH']
        result = run_group(['nice', '-n', '10', *map(str, args)], cwd=root, env=env, timeout=120, capture=True)
        assert result.returncode == 0 and not result.timed_out, (args, result.stdout, result.stderr)

    if simulator == 'icarus':
        assert vcd.tool('iverilog') and vcd.tool('vvp'), 'Icarus is required for simulator evidence'
        run([vcd.tool('iverilog'), '-g2012', '-o', root / 'run', source])
        run([vcd.tool('vvp'), root / 'run', *(['-fst'] if fmt == 'fst' else [])])
    else:
        assert vcd.tool('verilator'), 'Verilator is required for simulator evidence'
        flags = []
        # Homebrew keeps lz4 headers and libraries outside the compiler default paths.
        lz4 = Path('/opt/homebrew/opt/lz4')
        if fmt == 'fst' and (lz4 / 'include/lz4.h').exists():
            flags = ['-CFLAGS', f'-I{lz4 / "include"}', '-LDFLAGS', f'-L{lz4 / "lib"} -llz4']
        run([vcd.tool('verilator'), '--binary', '--timing', '--trace-fst' if fmt == 'fst' else '--trace', *flags,
             '-j', '1', '--Mdir', root / 'obj', '--top-module', 'arrays', source])
        run([root / 'obj' / 'Varrays'])
    assert wave.is_file()
    return str(wave)


def test_simulator_array_queries_and_cuts(simulator_wave, tmp_path, rvw):
    wave = simulator_wave
    variables = {v.name: v for v in ops.list_signals(wave)}
    # Verilator uses unescaped references; Icarus uses escaped references.
    names = {}
    for stem in ('a', 'words'):
        for i in range(2):
            candidates = [n for n in variables if n.split('.')[-1].lstrip('\\') == f'{stem}[{i}]']
            assert len(candidates) == 1, variables
            names[stem, i] = candidates[0]
    expected0 = {names['a', 0]: 0, names['a', 1]: 1, names['words', 0]: 2, names['words', 1]: 5}
    expected5 = {names['a', 0]: 1, names['a', 1]: 0, names['words', 0]: 9, names['words', 1]: 10}
    regex = r'(?:a|words)\[[01]\]$'
    def sampled(path, at):
        return {n: vcd.to_int(raw) for n, raw in ops.sample_raw(path, list(expected0), at).items()}
    assert sampled(wave, 0) == expected0
    assert sampled(wave, 5) == expected5
    assert {r['signal'] for r in ops.changes(wave, regex)} == set(expected0)
    # Searches may read FST natively (wellen); names and values must match the converter path.
    from rvw.wave import search
    edges = {r['signal']: r['changes'] for r in search.edges(wave, regex)['signals']}
    assert set(edges) == set(expected0)
    assert search.find(wave, f"`{names['words', 1]}` == 10")['first'] == 5
    group = {'name': 'bits', 'scope': r'^.*\.', 'counts': {'valid': r'\\?a\[[01]\]'}}
    assert snapshot.take([group], wave, 0)[0]['counts']['valid'] == '1/2'
    assert rvw('wave', 'sample', wave, regex, '--at', 0, '--json')[2]['values'] == ops.sample(wave, regex, 0)
    registry, problems = Registry.discover({'wave'})
    assert not problems
    try:
        _, result, error = registry.call_json('wave_sample', {'wave': wave, 'regex': regex, 'at': '0'})
        assert not error and result['values'] == ops.sample(wave, regex, 0)
    finally:
        registry.jobs.shutdown()
    for suffix in ('.vcd', '.fst'):
        cut = str(tmp_path / ('cut' + suffix))
        ops.cut(wave, cut, 0, 10, regex=regex)
        assert sampled(cut, 0) == expected0
        assert sampled(cut, 5) == expected5
        assert snapshot.take([group], cut, 5)[0]['counts']['valid'] == '1/2'
