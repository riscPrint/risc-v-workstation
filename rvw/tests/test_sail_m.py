import pytest
from rvw.formal.sail_m import lower
from rvw.formal.isa_activation import cover_source
pytestmark=pytest.mark.fast


def test_signedness_cast_lowering_does_not_corrupt_unsigned():
    text=lower("x = unsigned'(64'(signed'({a})));",'mul')
    assert text == "x = $unsigned(64'($signed({a})));"
    assert 'un$signed' not in text


def test_packed_assignment_and_multiline_temporary():
    assert "'{" not in lower("x = '{a,b};",'mul')
    assert "x = 32'({a\n*b});" == lower('x = {a\n*b}[31:0];','mul')


def test_integer_primitive_is_bound_not_blackboxed():
    text=lower('quot_round_zero instance(a,b,out);','div')
    assert 'module sail_div_quot_round_zero' in text
    assert '$signed(a) / $signed(b)' in text


def test_activation_retains_check_source_and_assumptions():
    source='[options]\nmode bmc\ndepth 60\nskip 59\n[engines]\nabc bmc3\n[script]\nread -formal design.sv\n[file design.sv]\nalways @* assume(reset == $initstate);\n'
    result=cover_source(source,'bitwuzla')
    assert 'mode cover' in result and 'skip 59' not in result
    assert 'smtbmc bitwuzla' in result
    assert 'assume(reset == $initstate)' in result
    assert 'depth 60' in result


def test_sail_m_discovery():
    from rvw.cli import build_parser
    from rvw.formal.commands.sail_m import mcp_tools
    args=build_parser().parse_args(['formal','sail-m','--model','x','--out','y'])
    assert args.compiler=='sail'
    assert mcp_tools()[0].name=='formal_sail_m'


def test_changed_sail_source_stops_before_compiler(tmp_path):
    from rvw.formal.sail_m import generate, PATHS
    for name in PATHS:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('changed source')
    with pytest.raises(ValueError,match='hash mismatch'):
        generate(tmp_path,'missing-compiler',tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('trace',[False,True])
def test_native_pass_without_cover_trace_does_not_activate(tmp_path,monkeypatch,trace):
    import json
    from rvw.formal.isa_activation import run
    from rvw.common.proc import Result
    import rvw.formal.isa_activation as module
    work=tmp_path/'riscv-formal/cores/project/checks';work.mkdir(parents=True)
    (work/'insn_mul_ch0.sby').write_text('[options]\nmode bmc\ndepth 60\n[engines]\nabc bmc3\n[script]\nread -formal a.sv\n')
    (tmp_path/'results.json').write_text(json.dumps(dict(tests=[dict(id='insn_mul_ch0',status='pass')])))
    def fake(*a,**k):
        target=work/'insn_mul_ch0-activation';target.mkdir()
        (target/'status').write_text('PASS')
        if trace:
            (target/'engine_0').mkdir();(target/'engine_0/trace0.vcd').write_text('#0\n')
        return Result(0)
    monkeypatch.setattr(module,'run_group',fake)
    entry=run({'solver':'bitwuzla'},tmp_path,1)['tests'][0]
    assert entry['instruction_activation']['status']==('reached' if trace else 'inconclusive')
    assert bool(entry.get('inconclusive')) != trace
