"""Keep arithmetic source boundaries separate from simulation and service code."""
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]
select = runpy.run_path(str(ROOT/'examples/naxriscv/formal/units.py'))['component_source']


def test_helper_selection_excludes_simulation_and_regfile_services():
    text = ('package old\nobject MulSpliter { val product=1 }\nobject AdderAggregator {\n'
            ' val sum=2\n  //Here is an example of usage.\n def main()={}\n}\ntrait Service{}')
    result = select('Misc.scala', text)
    assert 'val product=1' in result and 'val sum=2' in result
    assert 'def main' not in result and 'trait Service' not in result
    assert result.count('{') == result.count('}')


def test_divider_selection_preserves_component_and_refuses_missing_marker():
    result = select('DivRadix4.scala', 'import naxriscv.Global\ncase class DivRadix4{}\nobject DivRadix4Tester {}')
    assert 'case class DivRadix4{}' in result
    assert 'DivRadix4Tester' not in result and 'import naxriscv.Global' not in result
    with pytest.raises(ValueError, match='boundary changed'):
        select('DivRadix4.scala', 'case class Changed{}')
