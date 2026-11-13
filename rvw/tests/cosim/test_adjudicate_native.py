"""Native integration when Spike, Sail and the compiler are installed."""

def test_native_spike_and_sail_flow(tmp_path, tmp_path_factory, monkeypatch):
    from pathlib import Path
    import pytest
    from cosim_build import _build
    from model_fixtures import generate
    from rvw.cosim.platform import Platform
    from rvw.cosim.adjudicate import execute_json
    import os
    import shutil
    selected = os.environ.get('RVW_SAIL') or shutil.which('sail_riscv_sim')
    sail = Path(selected) if selected else None
    if sail is None or not sail.is_file():
        pytest.skip('native Sail executable not installed')
    monkeypatch.setenv('RVW_SAIL', str(sail))
    source = tmp_path/'both.S'
    source.write_text('''.section .text
.globl _start
_start:
 li a0, 7
 la t0, tohost
 li t1, 1
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
''')
    elf = _build(tmp_path_factory, source)
    trace = tmp_path/'trace.jsonl'
    assert generate(elf, trace, Platform.load('boom'), 100)['termination'] == 'pass'
    result = execute_json(elf=str(elf), trace=str(trace), core='boom', strict=True)
    assert result['status'] == 'match', result
    assert set(result['matched_references']) == {'spike', 'sail'}
