"""Native BMC witness and Yosys sim what-if tests. No core checkout needed."""
import json
import shutil
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal.cex import stimulus
from rvw.formal.mcp_tools import _argv, _runner, mcp_tools
from rvw.common.proc import run_group


@pytest.fixture(scope='module')
def proof(tmp_path_factory):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2', 'vcd2fst')):
        pytest.skip('needs native Yosys, SBY, Yices and vcd2fst')
    root = tmp_path_factory.mktemp('cex')
    rtl = root / 'Top.v'
    rtl.write_text('''module Top(input clk, input bad, input guard, output reg seen=0);
    always @(posedge clk) begin
      seen <= bad;
      assert(!bad);
      assume(!guard);
    end
    endmodule
    ''')
    assert main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'Top',
                 '--depth', '3', '--first-failure', '--out', str(root / 'proof')]) == 1
    result = json.loads((root / 'proof/result.json').read_text())
    assert result['status'] == 'fail'
    return root / 'proof'


def replay(proof, out, *options):
    assert main(['formal', 'cex', '--result', str(proof), '--out', str(out), *options]) == 1
    return json.loads((out / 'result.json').read_text())


def test_native_original_and_edit(proof, tmp_path):
    original = (proof / 'sby/engine_0/trace.vcd').read_bytes()
    same = replay(proof, tmp_path / 'same')
    assert same['disposition'] == 'reproduced'
    changed = replay(proof, tmp_path / 'changed', '--edit', 'bad@0=0')
    assert changed['disposition'] == 'failure_not_observed'
    assert changed['status'] == 'inconclusive'
    assert Path(changed['wave']).is_file() and Path(changed['fst']).is_file()
    assert (proof / 'sby/engine_0/trace.vcd').read_bytes() == original
    captured = changed['input_capture']['files']
    assert any(x['source'].endswith('design.il') for x in captured)
    assert any(x['source'].endswith('Top.v') for x in captured)


def test_assumption_violation_is_inconclusive(proof, tmp_path):
    result = replay(proof, tmp_path / 'invalid', '--edit', 'guard@0=1')
    assert result['disposition'] == 'inconclusive'
    assert any(x['type'] == '$assume' for x in result['edited']['assertions'])


@pytest.mark.parametrize('edit', ['seen@0=0', 'bad@1=0', 'bad@0=2', 'bad@0=-1', 'bad=0'])
def test_invalid_edits(proof, tmp_path, edit):
    with pytest.raises(SystemExit) as exc:
        main(['formal', 'cex', '--result', str(proof), '--out', str(tmp_path / 'out'), '--edit', edit])
    assert exc.value.code == 2
    assert not (tmp_path / 'out/result.json').exists()


def test_original_directory_is_preserved(proof):
    original = (proof / 'result.json').read_bytes()
    with pytest.raises(SystemExit):
        main(['formal', 'cex', '--result', str(proof), '--out', str(proof)])
    assert (proof / 'result.json').read_bytes() == original


def test_mcp_native(proof, tmp_path):
    class Job:
        def run(self, argv):
            return run_group(argv, capture=True, timeout=60).returncode
        def tail(self, n):
            return ''
    result = _runner('cex')(Job(), result=str(proof), out=str(tmp_path / 'mcp'), edit=['bad@0=0'])
    assert result['disposition'] == 'failure_not_observed'
    assert 'formal_cex' in {t.name for t in mcp_tools()}
    assert _argv('cex', {'open': True})[-1] == '--open'


def test_native_failure_stays_inconclusive(proof, tmp_path, monkeypatch):
    import rvw.formal.cex as cex
    native = cex.run_group
    def fail(argv, **kwargs):
        if 'vcd2fst' in argv[0]:
            from rvw.common.proc import Result
            return Result(1)
        return native(argv, **kwargs)
    monkeypatch.setattr(cex, 'run_group', fail)
    result = replay(proof, tmp_path / 'failed')
    assert result['disposition'] == 'inconclusive'
    assert 'vcd2fst' in result['error']


def test_navigation_uses_captured_metadata(proof, tmp_path, monkeypatch):
    import rvw.formal.cex as cex
    from rvw.common.proc import Result
    hgldd = tmp_path / 'hgldd'
    hgldd.mkdir()
    (hgldd / 'Top.dd').write_text('{}')
    pdg = tmp_path / 'pdg.json'
    pdg.write_text('{}')
    native = cex.run_group
    commands = []
    # Fake optional viewers test wiring only. Native wave replay still runs.
    def fake(argv, **kwargs):
        if argv[0] == '/bin/echo':
            commands.append(argv)
            if 'dyn-pdg' in argv:
                Path(argv[argv.index('-o') + 1]).write_text('{}')
            return Result(0, stdout='wiring only')
        return native(argv, **kwargs)
    real_which = shutil.which
    monkeypatch.setattr(cex, 'run_group', fake)
    monkeypatch.setattr(shutil, 'which', lambda n: '/bin/echo' if n in ('spinaltrace-cli', 'spinalwaves-check') else real_which(n))
    result = replay(proof, tmp_path / 'nav', '--hgldd', str(hgldd), '--pdg', str(pdg),
                    '--criterion', 'line:Top.scala:4', '--at-time', '9')
    nav = result['navigation']
    assert nav['types']['status'] == 'completed'
    assert nav['causes']['status'] == 'completed'
    assert any('baseline/wave.vcd' in a for a in commands[1])
    assert str(pdg) not in commands[1]
    assert nav['surfer_command'][0] == 'surfer-tywaves'


def test_model_probe_failure_is_inconclusive(proof, tmp_path, monkeypatch):
    import rvw.formal.cex as cex
    from rvw.common.proc import Result
    monkeypatch.setattr(cex, 'run_group', lambda *a, **kw: Result(1))
    result = replay(proof, tmp_path / 'probe-failed')
    assert result['disposition'] == 'inconclusive'
    assert 'Yosys replay failed' in result['error']
