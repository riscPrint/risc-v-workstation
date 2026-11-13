import json
import pytest
from rvw.cli import main
pytestmark = pytest.mark.fast

def test_unsupported_source_is_structured_and_preserves_output(tmp_path, capsys):
    source = tmp_path / 'source.sv'
    source.write_text('`define WORD 32\nmodule top; endmodule\n')
    out = tmp_path / 'lowered.sv'
    out.write_text('keep me')
    assert main(['formal', 'sva-lower', str(source), '--out', str(out)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'unsupported'
    assert result['construct'] == 'preprocessor'
    assert out.read_text() == 'keep me'

def test_missing_source_is_structured(tmp_path, capsys):
    assert main(['formal', 'sva-lower', str(tmp_path / 'absent'), '--out', str(tmp_path / 'out')]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'
