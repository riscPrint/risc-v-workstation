from pathlib import Path
import pytest
from rvw.common.capture import Capture
from rvw.query.hdl_slang import capture_sources
pytestmark = pytest.mark.fast

def test_self_contained_rtl_does_not_capture_build_output(tmp_path):
    core = tmp_path / 'core'
    core.mkdir()
    source = core / 'core.sv'
    source.write_text('module core; endmodule')
    (core / 'out').mkdir()
    (core / 'out/large.vcd').write_bytes(b'x' * 8192)
    capture = Capture(tmp_path / 'capture', max_tree_bytes=1024)
    copies, includes, used = capture_sources(capture, [source], [])
    assert copies[0].read_text() == source.read_text()
    assert includes == []
    assert len(used) == 1 and used[0].source == str(source)
