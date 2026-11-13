"""Project adapter generation and optional native good/bad controls."""
import importlib.util
import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'Uvm/examples/custom_bus/run.py'
spec = importlib.util.spec_from_file_location('custom_bus_run', SOURCE)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


def test_project_adapter_preserves_custom_pins_and_scenario(tmp_path):
    generated = example.prepare(tmp_path/'project')
    bench = Path(generated['manifest']).parent
    config = json.loads((bench/'bindings.json').read_text())
    assert generated['profile'] == 'apb'
    assert config['bus']['class_name'] == 'project-owned'
    assert config['project_adapter']['bindings']['paddr'] == 'location'
    assert config['project_adapter']['bindings']['pready'] == 'done'
    assert (bench/'scenario.py').read_bytes() == (SOURCE.parent/'scenario.py').read_bytes()
    with pytest.raises(FileExistsError):
        example.prepare(tmp_path/'project')
