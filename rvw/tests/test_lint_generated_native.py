"""Run a minimal emitted-Verilog idiom through pinned native style lint."""
from pathlib import Path
import shutil
import pytest
from rvw.lint import native


@pytest.mark.native_light('Verible')
def test_always_star_is_generated_style_advice():
    if not shutil.which('verible-verilog-lint'):
        pytest.skip('Verible is not installed')
    source = str(Path(__file__).parent / 'fixtures/lint/generated_advice.v')
    r = native.run('verible', [source], 'GeneratedAdvice', 20)
    assert r['status'] == 'completed'
    assert any(f['rule'] == 'verible.always-comb' and f['severity'] == 'warning' for f in r['findings'])
    native.summarize_generated(r, [source])
    assert any(f['rule'] == 'verible.always-comb' and f['severity'] == 'info' for f in r['findings'])
