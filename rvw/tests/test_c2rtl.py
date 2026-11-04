"""Native C compilation and SBY checks for the small datapath flow."""
import importlib.util
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2] / 'SpinalChecks/c2rtl'
spec = importlib.util.spec_from_file_location('c2rtl_check', ROOT / 'check.py')
flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)

native = pytest.mark.skipif(any(not shutil.which(t) for t in
    ('clang', 'yosys', 'sby', 'yices-smt2')), reason='native formal tools required')


def check(tmp_path, op='add', rtl=None, model=None, timeout=30):
    if rtl is not None:
        rtl_path = tmp_path / 'input.v'
        rtl_path.write_text(rtl)
    else:
        rtl_path = ROOT / 'examples' / (op + '.v')
    if model is not None:
        model_path = tmp_path / 'input.c'
        model_path.write_text(model)
    else:
        model_path = ROOT / 'examples' / (op + '.c')
    return flow.run(SimpleNamespace(out=tmp_path / 'out', width=4, timeout=timeout,
                                   rtl=rtl_path, model=model_path))


@native
@pytest.mark.parametrize('op', ['add', 'shl', 'mul'])
def test_proved(tmp_path, op):
    r = check(tmp_path, op)
    assert r['status'] == 'proved', r
    assert r['depth'] == 1 and r['input_pairs'] == 256


@native
@pytest.mark.parametrize('op,expr', [('add', 'a ^ b'), ('shl', 'a << b'),
                                    ('mul', '(a * b) + 1')])
def test_independent_mutants(tmp_path, op, expr):
    r = check(tmp_path, op, f'module dut(input [3:0] a,b, output [3:0] y); '
                          f'assign y = {expr}; endmodule')
    assert r['status'] == 'counterexample', r
    assert r['traces']


@native
@pytest.mark.parametrize('model', [
    'uint32_t reference(uint32_t a,uint32_t b) { return a << (b+32u); }',
    'uint32_t reference(uint32_t a,uint32_t b) { return a+b+256u; }',
])
def test_invalid_oracle(tmp_path, model):
    r = check(tmp_path, model=model)
    assert r['status'] == 'inconclusive', r


@native
@pytest.mark.parametrize('rtl', [
    'module dut(input [3:0] a,b, output reg [3:0] y); always @(posedge a[0]) y<=b; endmodule',
    'module dut(input [3:0] a,b, output [3:0] y); assign y=a+b; always @* assume(a==0); endmodule',
    'module dut(input signed [3:0] a,b, output [3:0] y); assign y=a+b; endmodule',
    'module dut(input [3:0] a,b, output [3:0] y); endmodule',
    'module dut(input [3:0] a,b, output [3:0] y); missing u(a,b,y); endmodule',
])
def test_unsupported_design(tmp_path, rtl):
    r = check(tmp_path, rtl=rtl)
    assert r['status'] == 'inconclusive', r


@native
def test_timeout(tmp_path):
    assert check(tmp_path, timeout=0.000001)['status'] == 'inconclusive'


def test_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(flow.shutil, 'which', lambda _: None)
    assert check(tmp_path)['status'] == 'inconclusive'


def test_table_must_be_complete():
    with pytest.raises(ValueError):
        flow.parse_table('0 0 0\n', 4)
    with pytest.raises(ValueError):
        flow.parse_table('\n'.join(f'{a} {b} 16' for a in range(16) for b in range(16)), 4)


def test_existing_output_is_preserved(tmp_path):
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'result.json').write_text('old')
    with pytest.raises(FileExistsError):
        check(tmp_path)
    assert (out / 'result.json').read_text() == 'old'


@native
@pytest.mark.parametrize('status,code,timed_out', [('FAIL', 2, False),
    ('PASS', 1, False), ('PASS', 0, True), ('UNKNOWN', 0, False), ('', 0, False)])
def test_incomplete_solver_evidence(tmp_path, monkeypatch, status, code, timed_out):
    original = flow.run_group

    def execute(argv, **kwargs):
        if '-f' in argv and 'check.sby' in argv:
            directory = Path(kwargs['cwd']) / 'check'
            directory.mkdir()
            (directory / 'status').write_text(status)
            return SimpleNamespace(returncode=code, timed_out=timed_out, stdout='', stderr='')
        return original(argv, **kwargs)

    monkeypatch.setattr(flow, 'run_group', execute)
    assert check(tmp_path)['status'] == 'inconclusive'


@pytest.mark.parametrize('width', [-1, 0, 5])
def test_invalid_width(tmp_path, width):
    args = SimpleNamespace(out=tmp_path / 'out', width=width, timeout=30,
                           model='', rtl='')
    assert flow.run(args)['status'] == 'inconclusive'


@native
@pytest.mark.parametrize('model', [
    'uint64_t reference(uint32_t a,uint32_t b) { return a+b; }',
    'int reference(uint32_t a,uint32_t b) { return (int)((a+b)&15); }',
    'double reference(uint32_t a,uint32_t b) { return a+b; }',
    'uint32_t reference(uint64_t a,uint64_t b) { return (a+b)&15; }',
])
def test_oracle_interface_is_exact(tmp_path, model):
    r = check(tmp_path, model=model)
    assert r['status'] == 'inconclusive'
    assert 'compile failed' in r['reason']
    assert not (tmp_path / 'out/check.sby').exists()


@native
@pytest.mark.parametrize('operation', [
    'a / b',
    '(uint32_t)((int32_t)2147483647 + (int32_t)a)',
    '(uint32_t)((int32_t)-1 << b)',
])
def test_undefined_oracles_never_reach_solver(tmp_path, operation):
    model = 'uint32_t reference(uint32_t a,uint32_t b) { (void)a; (void)b; return (' + operation + ') & 15u; }'
    r = check(tmp_path, model=model)
    assert r['status'] == 'inconclusive'
    assert 'table failed' in r['reason']
    assert not (tmp_path / 'out/check.sby').exists()
