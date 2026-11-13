import json
import pytest
from rvw.cosim.platform import Platform

pytestmark = pytest.mark.fast

@pytest.mark.parametrize("value", [False, True])
def test_split_ram_is_explicit(tmp_path, value):
    p = tmp_path / "platform.json"
    p.write_text(json.dumps(dict(name="test", xlen=32, isa="rv32i", reset_pc=0x80000000,
                                ram=[dict(base=0x80000000,size=4096)], mmio=[], scalar_split_ram=value)))
    assert Platform.load("test", p).scalar_split_ram is value
    data=json.loads(p.read_text());data.pop("scalar_split_ram");p.write_text(json.dumps(data))
    assert Platform.load("test", p).scalar_split_ram is False

@pytest.mark.parametrize("value", [0,1,"true",None,{}])
def test_split_ram_rejects_non_boolean(tmp_path, value):
    p=tmp_path / "platform.json"
    p.write_text(json.dumps(dict(name="test", xlen=32, isa="rv32i", reset_pc=0x80000000,
                                ram=[],mmio=[],scalar_split_ram=value)))
    with pytest.raises(ValueError, match="scalar_split_ram must be a boolean"):
        Platform.load("test",p)
