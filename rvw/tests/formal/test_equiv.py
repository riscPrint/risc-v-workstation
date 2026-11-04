import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal.equiv import verdict

TOOLS = all(shutil.which(t) for t in ('eqy', 'sby', 'yosys', 'yosys-abc', 'yices-smt2'))


@pytest.mark.skipif(not TOOLS, reason='needs native formal tools')
@pytest.mark.parametrize('change,manual,expected', [(False, False, 'equivalent'), (True, False, 'not_equivalent'), (False, True, 'equivalent')])
def test_native_equiv(tmp_path, change, manual, expected):
    gold = tmp_path / 'gold.v'
    gate = tmp_path / 'gate.v'
    gold.write_text('module top(input clk, reset, input [3:0] a, output reg [3:0] q); always @(posedge clk) q <= reset ? 0 : a + 1; endmodule')
    # Same function through a different Boolean expression. Renaming exercises manual mapping.
    name = 'stage' if manual else 'q'
    gate.write_text(f'module top(input clk, reset, input [3:0] a, output [3:0] q); reg [3:0] {name if manual else "state"}; '
                    f'assign q = {name if manual else "state"}; always @(posedge clk) {name if manual else "state"} <= reset ? 0 : a - {"14" if change else "15"}; endmodule')
    out = tmp_path / 'out'
    args = ['formal', 'equiv', '--gold', str(gold), '--gate', str(gate), '--top', 'top', '--reset', 'reset', '--out', str(out)]
    # Alias q names the state on each side. Force a visible internal register to test pairing separately below.
    rc = main(args)
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == expected, result
    assert rc == (0 if expected == 'equivalent' else 1)
    assert result['partitions']
    assert all(not p['crossbits'] for p in result['partitions'])
    if change:
        assert result['traces']


def test_verdict_never_promotes_missing_evidence():
    passed = [{'status': 'PASS'}]
    assert verdict(0, False, passed, {'gold': ['q']}, []) == 'inconclusive'
    assert verdict(0, True, passed, {}, []) == 'inconclusive'
    assert verdict(0, False, [], {}, []) == 'inconclusive'
    assert verdict(0, False, [{'status': 'UNKNOWN'}], {}, []) == 'inconclusive'
    assert verdict(1, False, [{'status': 'FAIL'}], {}, []) == 'inconclusive'


def test_manual_mapping():
    from rvw.formal.equiv import mapping
    pairs, missing = mapping({'q': (1, 2)}, {'stage': (4, 5)}, ['q=stage'])
    assert pairs == [{'gold': 'q', 'gate': 'stage', 'width': 2, 'method': 'manual'}]
    assert missing == {'gold': [], 'gate': []}
    assert mapping({'q': (1,)}, {'stage': (2,)}, [])[1] == {'gold': ['q'], 'gate': ['stage']}

@pytest.mark.skipif(not TOOLS, reason='needs native formal tools')
def test_retiming_and_dsec(tmp_path):
    gold = tmp_path / 'gold.v'
    gate = tmp_path / 'gate.v'
    gold.write_text('module top(input clk, input [3:0] a, output reg [3:0] q); reg [3:0] p; always @(posedge clk) begin p <= a; q <= p + 1; end endmodule')
    gate.write_text('module top(input clk, input [3:0] a, output reg [3:0] q); reg [3:0] p; always @(posedge clk) begin p <= a + 1; q <= p; end endmodule')
    out = tmp_path / 'out'
    assert main(['formal', 'equiv', '--gold', str(gold), '--gate', str(gate), '--top', 'top', '--settle', '2', '--dsec', '--out', str(out)]) == 0
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'equivalent'
    assert result['dsec']['exit'] == 0
    assert 'Networks are equivalent' in (out / 'dsec.log').read_text()


@pytest.mark.skipif(not TOOLS, reason='needs native formal tools')
def test_renamed_state_needs_pair(tmp_path):
    a, b = tmp_path / 'a.v', tmp_path / 'b.v'
    a.write_text('module top(input clk, input a, output q); reg old; always @(posedge clk) old <= a; assign q = !old; endmodule')
    b.write_text(a.read_text().replace('old', 'newreg'))
    out = tmp_path / 'out'
    args = ['formal', 'equiv', '--gold', str(a), '--gate', str(b), '--top', 'top', '--settle', '1', '--out', str(out)]
    assert main(args) == 1
    assert json.loads((out / 'result.json').read_text())['unmatched'] == {'gold': ['old'], 'gate': ['newreg']}
    assert main(args + ['--pair', 'old=newreg']) == 0
    assert json.loads((out / 'result.json').read_text())['state_mapping'][0]['method'] == 'manual'

@pytest.mark.skipif(not TOOLS, reason='needs native formal tools')
@pytest.mark.parametrize('kind', ['timeout', 'blackbox', 'assumption'])
def test_unsupported_or_timeout_is_inconclusive(tmp_path, monkeypatch, kind):
    from rvw.formal import common
    source = tmp_path / 'top.v'
    text = 'module top(input clk, a, output reg q); always @(posedge clk) q <= a; endmodule'
    if kind == 'blackbox':
        text = '(* blackbox *) module box(input a, output q); endmodule\nmodule top(input clk, a, output q); box b(a,q); endmodule'
    if kind == 'assumption':
        text = text.replace('endmodule', 'always @* assume(0); endmodule')
    source.write_text(text)
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'result.json').write_text('{"status":"equivalent"}')
    if kind == 'timeout':
        original = common.run
        def run(cmd, *args, **kwargs):
            return (124, 0.1) if cmd[0] == 'eqy' else original(cmd, *args, **kwargs)
        monkeypatch.setattr(common, 'run', run)
    assert main(['formal', 'equiv', '--gold', str(source), '--gate', str(source), '--top', 'top', '--settle', '1', '--out', str(out)]) == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'inconclusive'
    assert not (out / 'dsec.log').exists()


def test_clock_cannot_be_used_as_generated_reset(tmp_path):
    source = tmp_path / 'top.v'
    source.write_text('module top(input clk, a, output reg q); always @(posedge clk) q <= a; endmodule')
    out = tmp_path / 'out'
    assert main(['formal', 'equiv', '--gold', str(source), '--gate', str(source), '--top', 'top', '--reset', 'clk', '--out', str(out)]) == 1
    assert 'different inputs' in json.loads((out / 'result.json').read_text())['reason']


def test_dsec_unknown_is_not_a_completed_comparison(tmp_path, monkeypatch):
    from rvw.formal import common
    from rvw.formal.equiv import dsec
    for side in ('gold', 'gate'):
        (tmp_path / side).mkdir()
    def fake_run(cmd, cwd, log, timeout):
        log.write_text('Networks are UNDECIDED. Time limit reached.\n')
        return 0, 0.1
    monkeypatch.setattr(common, 'run', fake_run)
    with pytest.raises(ValueError, match='did not complete'):
        dsec(tmp_path, lambda: 1)


@pytest.mark.skipif(not TOOLS, reason='needs native formal tools')
@pytest.mark.parametrize('latency,mutant,expected', [(1, False, 'equivalent'),
    (0, False, 'not_equivalent'), (1, True, 'not_equivalent'), (2, False, 'not_equivalent')])
def test_explicit_candidate_latency(tmp_path, latency, mutant, expected):
    gold, gate = tmp_path / 'gold.v', tmp_path / 'gate.v'
    gold.write_text('module top(input clk, reset, input [3:0] a, output reg [3:0] q); '
                    'always @(posedge clk) q <= reset ? 0 : a+1; endmodule')
    gate.write_text('module top(input clk, reset, input [3:0] a, output reg [3:0] q); '
                    'reg [3:0] stage; always @(posedge clk) begin '
                    f'stage <= reset ? 0 : a+{2 if mutant else 1}; '
                    'q <= reset ? 0 : stage; end endmodule')
    out = tmp_path / 'out'
    rc = main(['formal', 'equiv', '--gold', str(gold), '--gate', str(gate), '--top', 'top',
               '--reset', 'reset', '--settle', '2', '--latency', str(latency),
               '--unmatched-state', 'prove', '--timeout', '30', '--out', str(out)])
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == expected, result
    assert rc == (0 if expected == 'equivalent' else 1)
    assert result['unmatched']['gate'] == ['stage']
    assert result['restrictions']['latency'] == latency
    assert all(p['crossbits'] == {} for p in result['partitions'])


@pytest.mark.parametrize('latency', [-1, 65])
def test_invalid_latency_cannot_publish_equivalence(tmp_path, latency):
    out = tmp_path / 'out'
    assert main(['formal', 'equiv', '--gold', 'missing.v', '--gate', 'missing.v', '--top', 'top',
                 '--latency', str(latency), '--out', str(out)]) == 1
    assert json.loads((out / 'result.json').read_text())['status'] == 'inconclusive'
