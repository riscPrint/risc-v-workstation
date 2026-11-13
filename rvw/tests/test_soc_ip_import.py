"""External import records exact bytes and refuses missing or ambiguous bindings."""
from pathlib import Path
import json
import pytest
from rvw.soc.ip_import import import_ip

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]


def descriptor(tmp_path):
    source=tmp_path/'ip.toml'
    source.write_text('''schema="rvw.soc-ip/1"
name="timer"
module="timer"
bus="apb3"
window_size=256
address_bits=8
data_bits=32
sources=["timer.v"]
registers=[]
[signals]
clock="clk"
reset="rst"
address="addr"
wdata="wd"
rdata="rd"
write="we"
select="sel"
enable="en"
ready="ack"
''')
    (tmp_path/'timer.v').write_text('`include "header.v"\nmodule timer; endmodule\n')
    (tmp_path/'header.v').write_text('// external header\n')
    return source


def test_sources_and_register_contract(tmp_path):
    source=descriptor(tmp_path)
    result=import_ip(source,tmp_path,tmp_path/'out',0x10000000)
    assert set(result['sources'])=={'timer.v','header.v'}
    assert result['binder']['class']=='imported.timer'
    assert result['validation']=='generated_only'
    assert 'external header' in (tmp_path/'out/bundle.v').read_text()
    assert '.sel(selected)' in (tmp_path/'out/bridge.v').read_text()
    (tmp_path/'header.v').write_text('// changed\n')
    other=import_ip(source,tmp_path,tmp_path/'other',0x10000000)
    assert result['sources']['header.v']!=other['sources']['header.v']


def test_missing_source_does_not_publish(tmp_path):
    source=descriptor(tmp_path);(tmp_path/'header.v').unlink()
    with pytest.raises(FileNotFoundError):import_ip(source,tmp_path,tmp_path/'out',0x10000000)
    assert not (tmp_path/'out').exists()


def test_missing_bus_role_does_not_publish(tmp_path):
    source=descriptor(tmp_path);source.write_text(source.read_text().replace('ready="ack"',''))
    with pytest.raises(ValueError,match='required'):import_ip(source,tmp_path,tmp_path/'out',0x10000000)
    assert not (tmp_path/'out').exists()


def test_recursive_include_refused(tmp_path):
    source=descriptor(tmp_path);(tmp_path/'header.v').write_text('`include "timer.v"\n')
    with pytest.raises(ValueError,match='recursive'):import_ip(source,tmp_path,tmp_path/'out',0x10000000)


def test_mcp_and_cli(tmp_path):
    from rvw.soc.commands.ip_import import mcp_tools
    # Import the descriptor through the same handler used by the public command.
    source=descriptor(tmp_path)
    result=mcp_tools()[0].handler(source=str(source),root=str(tmp_path),out=str(tmp_path/'out'),base=0x10000000)
    assert result['status']=='generated'
