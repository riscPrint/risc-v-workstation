import pytest
from rvw.query.hdl import strip_comments, SOURCE_REMAP
import re
pytestmark = pytest.mark.fast

def test_file_input_comment_is_not_active_hdl():
    text='// $readmemh is not used\nmodule top; /* `line 7 */ endmodule'
    assert not re.search(SOURCE_REMAP,strip_comments(text))
    assert strip_comments(text).count('\n') == text.count('\n')

@pytest.mark.parametrize('text',['$readmemh("a", mem);','`line 1 "file"','a``b','"//"; $fopen("x");'])
def test_file_inputs_and_remaps_still_refused(text):
    assert re.search(SOURCE_REMAP,strip_comments(text))
