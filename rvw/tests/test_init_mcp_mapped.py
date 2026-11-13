import pytest
from rvw.init.mcp_tools import _scaffold, mcp_tools

pytestmark = pytest.mark.fast


def test_mcp_mapped_init(tmp_path):
    (tmp_path / 'build.sbt').write_text('ThisBuild / scalaVersion := "2.13.14"\nlazy val core = project\n')
    result = _scaffold(str(tmp_path), 'rv32im', spinal_top='Stepper', reset_pc='0x80000000',
                       buses=['mem:req-rsp:cmd_valid=req,address=addr,rsp_valid=rsp,rdata=data'],
                       rvfi_prefix='io_rvfi_', dry_run=True)
    assert result['mapped']
    assert result['rvfi_prefix'] == 'io_rvfi_'
    assert 'rvw/core-map.json' in result['files']
    assert not (tmp_path / 'rvw.toml').exists()


def test_mcp_schema_exposes_mapped_options():
    tool = mcp_tools()[0]
    assert 'spinal_top' in tool.input_schema['properties']
    assert 'buses' in tool.input_schema['properties']
