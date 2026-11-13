from pathlib import Path
import pytest
from rvw.formal.riscv_proof import inline

pytestmark = pytest.mark.fast


def test_preserve_unbounded_and_initstate(tmp_path):
    (tmp_path/'defines.sv').write_text('`define RISCV_FORMAL_UNBOUNDED\n')
    (tmp_path/'checker.sv').write_text('`include "defines.sv"\nalways @* assume(reset == $initstate);\n')
    text = inline(tmp_path/'checker.sv', tmp_path)
    assert '`include' not in text
    assert '`define RISCV_FORMAL_UNBOUNDED' in text
    assert '$initstate' in text


def test_refuse_include_cycle(tmp_path):
    (tmp_path/'a.sv').write_text('`include "a.sv"')
    with pytest.raises(ValueError, match='recursive'):
        inline(tmp_path/'a.sv', tmp_path)


def test_refuse_selected_optional_assumptions(tmp_path):
    (tmp_path/'a.sv').write_text('`define RISCV_FORMAL_ASSUME\n`include "assume_stmts.vh"')
    with pytest.raises(ValueError, match='assume blocks'):
        inline(tmp_path/'a.sv', tmp_path)


def test_cli_and_mcp_discovery():
    from rvw.cli import build_parser
    from rvw.formal.commands.riscv_proof import mcp_tools
    assert mcp_tools()[0].name == 'formal_riscv_proof'
    parser = build_parser()
    args = parser.parse_args(['formal','riscv-proof','--out','x','--checks','insn_add_ch0'])
    assert args.engines == 'abc:pdr,smtbmc:yices'


@pytest.mark.parametrize('engines,timeout', [([], 1), (['abc:bmc3'], 1),
    (['abc:pdr']*2, 1), (['abc:pdr'], float('nan'))])
def test_refuse_invalid_proof_campaign_before_capture(tmp_path, engines, timeout):
    from rvw.formal.riscv_proof import run
    with pytest.raises(ValueError):
        run({}, tmp_path/'unused', engines, timeout)
    assert not (tmp_path/'unused').exists()


def test_do_not_silently_drop_consistency_checks(tmp_path):
    from rvw.formal.riscv_proof import capture
    with pytest.raises(ValueError, match='instruction checks only'):
        capture(dict(checks=['reg_ch0','cover']), tmp_path/'unused')
    assert not (tmp_path/'unused').exists()


@pytest.mark.parametrize('outcome,expected', [('fail','fail'), ('pass','inconclusive'), ('inconclusive','inconclusive')])
def test_preserve_portfolio_failures(tmp_path, monkeypatch, outcome, expected):
    import rvw.formal.riscv_proof as module
    import rvw.formal.portfolio as portfolio
    monkeypatch.setattr(module, 'capture', lambda cfg, out: dict(jobs=[dict(id='insn_add_ch0')], limits=[]))
    monkeypatch.setattr(portfolio, 'race', lambda *a, **k: dict(status=outcome))
    result = module.run({}, tmp_path, ['abc:pdr'], 1)
    assert result['status'] == expected
    assert result['rows'][0]['status'] == outcome
