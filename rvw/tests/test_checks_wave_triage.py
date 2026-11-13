"""Check pre-edge VCD sampling in the example triage helper."""
import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
spec = importlib.util.spec_from_file_location('triage_wave', Path(__file__).resolve().parents[2] /
    'examples/vexriscv/rvw/triage-wave.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_triage_uses_pre_edge_value_and_keeps_missing(tmp_path):
    wave = tmp_path / 'wave.vcd'
    wave.write_text('''$scope module TOP $end
$scope module Unit $end
$var wire 1 ! clk $end
$var wire 1 " fail $end
$var wire 1 # valid $end
$var wire 1 $ ready $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
0!
0"
1#
0$
#5
1!
#10
0!
1"
0#
#15
1!
0"
#20
0!
''')
    check = dict(id='hold', source=None, detail='strict', signals=dict(valid=['valid'], ready=['ready']))
    result = helper.extract(dict(toplevel='Unit', checks=[check]),
        dict(firings=[dict(id='hold', count=1, fail_signal='fail')]), wave, [])
    assert result['missing'] == []
    assert result['checks'][0]['samples'] == [
        dict(time_ps=5, signals=dict(valid='1', ready='0')),
        dict(time_ps=15, signals=dict(valid='0', ready='0'))]
    result = helper.extract(dict(toplevel='Unit', checks=[check]),
        dict(firings=[dict(id='hold', count=1, fail_signal='absent')]), wave, [])
    assert result['missing'] == ['hold']
