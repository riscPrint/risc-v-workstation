import json
import pytest
from rvw.formal.architectural_state import monitor, generate
pytestmark = pytest.mark.fast


def test_optional_halt_observation():
    text, widths, _ = monitor(32, halt=True)
    assert widths['halt'] == 1
    assert 'assign rvfi_halt = halt;' in text
    old, widths, _ = monitor(32)
    assert 'halt' not in widths
    assert 'assign rvfi_halt = 0;' in old


def test_simulation_assertions_stop_on_failure():
    text, _, _ = monitor(32)
    assert 'else $fatal(1, "architectural x0 changed")' in text
    assert 'else $fatal(1, "architectural register frame changed")' in text
    assert text.count('`ifdef YOSYS') == 2


def test_reset_polarity_is_explicit(tmp_path):
    plan = dict(schema='rvw.architectural-state/1', xlen=32, signals={}, reset_active_low='yes')
    path=tmp_path/'map.json';path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='reset_active_low'):
        generate(path,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_pico_snapshot_has_no_rvfi_aliases():
    from pathlib import Path
    import ast
    path=Path(__file__).resolve().parents[2]/'examples/picorv32/formal/prepare.py'
    tree=ast.parse(path.read_text())
    snapshots=[n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and
               any(isinstance(t,ast.Name) and t.id=='snapshot' for t in n.targets)]
    assert len(snapshots)==1
    assert 'rvfi_' not in snapshots[0]
    assert 'cpuregs[snapshot_i]' in snapshots[0]
