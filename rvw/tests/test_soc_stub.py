from pathlib import Path
import importlib.util
import pytest
from rvw.regress.config import load_config
from rvw.soc.compose import compose

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]


def test_stub_project(tmp_path):
    config=load_config(project=ROOT/'SpinalSoc/examples/stub/rvw.toml')
    assert config.name=='soc-stub'
    compose(ROOT/'SpinalSoc/examples/stub/compose.json',tmp_path/'soc')
    text=(tmp_path/'soc/ComposedSoc.scala').read_text()
    assert 'interrupt_7 := clint.io.irq' in text
    assert 'interrupt_11 := plic.io.irq' in text
    assert 'uart.io.serial.toIo()' in text
