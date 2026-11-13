"""Explicit state taint sources and bounded native policy checks."""
import json
import shutil

import pytest

from rvw.formal.security.ift import instrument
from rvw.formal.security.pair import proof_settings



def design():
    return {'modules': {'dut': {
        'ports': {'clk': {'direction': 'input', 'bits': [2]},
                  'd': {'direction': 'input', 'bits': [3]},
                  'q': {'direction': 'output', 'bits': [4]}},
        'netnames': {'csr': {'bits': [4]}, 'operand': {'bits': [3]}},
        'cells': {'reg': {'type': '$_DFF_P_', 'connections': {'C': [2], 'D': [3], 'Q': [4]}}}}}}


@pytest.mark.fast
def test_register_source_keeps_value_logic_and_forces_shadow():
    text = instrument(design(), 'dut', state_sources=['csr'])
    assert "assign q__t[0] = 1'b1;" in text
    assert 'n4 <= n3;' in text
    assert "1'b1 <=" not in text
    assert 't4' not in text


@pytest.mark.parametrize('names', [['absent'], ['operand'], ['csr', 'csr']])
@pytest.mark.fast
def test_state_source_requires_distinct_register_names(names):
    with pytest.raises(ValueError):
        instrument(design(), 'dut', state_sources=names)


@pytest.mark.parametrize('mode,depth', [('bmc', 0), ('bmc', 129), ('invalid', 8), ('bmc', True)])
@pytest.mark.fast
def test_bad_bounds_are_refused(mode, depth):
    with pytest.raises(ValueError):
        proof_settings({'mode': mode, 'depth': depth})


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')),
                    reason='native formal tools')
@pytest.mark.parametrize('leak', [False, True])
def test_native_csr_source_bounded_policy(tmp_path, leak):
    from rvw.cli import main
    rtl = tmp_path / 'dut.v'
    rtl.write_text('module dut(input clk,reset,d,output y,audit);reg csr;'
                   'always @(posedge clk) if(reset) csr<=0;else csr<=d;assign audit=csr;'
                   + ('assign y=csr;' if leak else "assign y=csr & 1'b0;") + 'endmodule')
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps({'clock': 'clk', 'reset': 'reset', 'sources': [],
                                 'internal_sources': ['csr'], 'sinks': ['y'],
                                 'mode': 'bmc', 'depth': 4, 'kind': 'secure_path',
                                 'adversary': 'CSR content is secret on every sample',
                                 'unmodeled_channels': ['physical']}))
    out = tmp_path / 'proof'
    rc = main(['formal', 'security', 'prove', '--rtl', str(rtl), '--top', 'dut',
               '--policy', str(policy), '--out', str(out), '--timeout', '30'])
    report = json.loads((out / 'result.json').read_text())
    assert report['status'] == ('fail' if leak else 'pass'), report
    assert report['proof_kind'] == 'bounded' and report['depth'] == 4
    assert rc == (1 if leak else 0)


@pytest.mark.fast
@pytest.mark.parametrize('extra,reason', [
    ({'source_regions': [{'source': 'data'}]}, 'alignment is unsupported'),
    ({'memory_map': 'true'}, 'memory_map must be Boolean'),
])
def test_unsupported_policy_options_are_not_ignored(tmp_path, extra, reason):
    from rvw.cli import main
    rtl = tmp_path / 'dut.v'
    rtl.write_text('module dut; endmodule')
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps(extra))
    out = tmp_path / 'proof'
    assert main(['formal', 'security', 'prove', '--rtl', str(rtl), '--top', 'dut',
                 '--policy', str(policy), '--out', str(out), '--timeout', '1']) == 1
    report = json.loads((out / 'result.json').read_text())
    assert report['status'] == 'inconclusive' and reason in report['reason']
