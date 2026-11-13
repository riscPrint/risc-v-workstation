"""Use only exact GHDL locator/statement pairs for coverage navigation."""
import pytest
from rvw.cov.code import SourceMap

pytestmark=pytest.mark.fast


def test_ghdl_exact_statement_and_no_nearest_guess(tmp_path):
    rtl=tmp_path/'lowered.v'
    rtl.write_text('/* rtl/cpu.vhd:42:3  */\nassign n1 = a;\n\nassign n2 = b;\n')
    smap=SourceMap(tmp_path)
    loc=smap.location({'f':'lowered.v','l':'2','t':'line'})
    assert (loc['file'],loc['line'])==('rtl/cpu.vhd',42)
    assert smap.location({'f':'lowered.v','l':'4','t':'line'}) is None
    assert smap.location({'f':'lowered.v','l':'3','t':'line'}) is None
