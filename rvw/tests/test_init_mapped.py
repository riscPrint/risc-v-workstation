"""`rvw init` mapped mode: a working C1 adapter description from one command, without native tools."""
import json

import pytest

pytestmark = pytest.mark.fast

from rvw.cli import main
from rvw.common.project import load_project
from rvw.common.proc import run_group
from rvw.cosim.platform import Platform
from rvw.init import mapped
from rvw.regress.config import load_config

RVFI = [dict(name='rvfi_' + f, dir='out', width=1 if f in ('valid', 'trap', 'halt', 'intr') else 32)
        for f in mapped.RVFI_FIELDS]
PICO_LIKE = [dict(name='clk', dir='in', width=1), dict(name='resetn', dir='in', width=1),
             dict(name='trap', dir='out', width=1), dict(name='mem_valid', dir='out', width=1),
             dict(name='mem_instr', dir='out', width=1), dict(name='mem_ready', dir='in', width=1),
             dict(name='mem_addr', dir='out', width=32), dict(name='mem_wdata', dir='out', width=32),
             dict(name='mem_wstrb', dir='out', width=4), dict(name='mem_rdata', dir='in', width=32),
             dict(name='irq', dir='in', width=32)] + RVFI


@pytest.fixture
def verilog_core(tmp_path, monkeypatch):
    root = tmp_path / 'vcore'
    root.mkdir()
    (root / 'core.v').write_text('module core(input clk); endmodule\n')
    monkeypatch.setattr(mapped, 'verilog_ports', lambda files, top, **_: PICO_LIKE)
    monkeypatch.setenv('RVW_HOME', str(tmp_path / 'installed workstation'))
    return root


def make(root, **extra):
    options = dict(isa='rv32i', verilog_top='core', verilog=[root / 'core.v'], clock='clk', reset='resetn',
                   reset_active='low', reset_pc='0x80000000', accept_platform_defaults=True)
    options.update(extra)
    return mapped.mapped_scaffold(root, **options)


def test_parse_bus_and_refusals():
    bus = mapped.parse_bus('d:req-rsp:cmd_valid=a,address=b,rsp_valid=c,rdata=d,write=w,write_response=1')
    assert bus['protocol'] == 'req-rsp' and bus['write_response'] and bus['signals']['write'] == 'w'
    with pytest.raises(ValueError, match='lacks'):
        mapped.parse_bus('d:req-rsp:cmd_valid=a')
    with pytest.raises(ValueError, match='unknown keys'):
        mapped.parse_bus('d:valid-ready:valid=a,ready=b,address=c,rdata=d,bogus=e')
    with pytest.raises(ValueError, match='protocol'):
        mapped.parse_bus('d:axi:valid=a')


def test_guess_finds_one_valid_ready_bus():
    buses = mapped.guess_buses(PICO_LIKE)
    assert buses == [dict(name='mem', protocol='valid-ready', write_response=False,
                          signals=dict(valid='mem_valid', ready='mem_ready', address='mem_addr',
                                       rdata='mem_rdata', wdata='mem_wdata', mask='mem_wstrb'))]


def test_verilog_project_loads_and_ties_unmapped_inputs(verilog_core):
    result = make(verilog_core, params=['PROGADDR_RESET=0x80000000'], defines=['RISCV_FORMAL'])
    assert result['status'] == 'created' and result['rvfi_prefix'] == 'rvfi_'
    assert result['unmapped_inputs'] == ['irq']
    core_map = json.loads((verilog_core / 'rvw/core-map.json').read_text())
    assert core_map['top']['files'] == ['../core.v']
    assert core_map['top']['parameters'] == {'PROGADDR_RESET': 0x80000000}
    assert core_map['top']['defines'] == {'RISCV_FORMAL': ''}
    assert core_map['constants'] == {'irq': '0x0'}
    assert core_map['rvfi'] == {'prefix': 'rvfi_'}
    config = load_config(project=verilog_core)
    project = load_project(verilog_core)
    assert config.source_env == 'RVW_CORE_SOURCE' and config.default_config == 'default'
    assert config.input_complete and 'RVW_CORE_MAP' in config.input_env
    assert project.get('query', 'build') == [str(verilog_core / 'rvw/build-db.sh')]
    platform = Platform.load('vcore', str(verilog_core / 'rvw/cosim.json'))
    assert platform.reset_pc == 0x80000000 and platform.xlen == 32
    info = run_group([str(verilog_core / 'rvw/run.sh'), 'info', '--json'], capture=True, text=True)
    assert info.returncode == 0 and json.loads(info.stdout)['mapped'] is True
    launcher = (verilog_core / 'rvw/run.sh').read_text()
    assert 'riscvsim.MappedMain' in launcher and 'RVW_CORE_MAP="$here/core-map.json"' in launcher
    assert 'query build-hdl' in (verilog_core / 'rvw/build-db.sh').read_text()
    assert 'ORIGIN = 0x80000000' in (verilog_core / 'rvw/programs/link.ld').read_text()


def test_platform_review_flag_without_acceptance(verilog_core):
    make(verilog_core, accept_platform_defaults=False)
    assert json.loads((verilog_core / 'rvw/cosim.json').read_text())['review_required'] is True
    with pytest.raises(ValueError):
        Platform.load('vcore', str(verilog_core / 'rvw/cosim.json'))


def test_mapping_errors_name_the_missing_port(verilog_core, monkeypatch):
    with pytest.raises(ValueError, match='does not have'):
        make(verilog_core, buses=['m:valid-ready:valid=mem_valid,ready=mem_ready,address=nope,rdata=mem_rdata'])
    monkeypatch.setattr(mapped, 'verilog_ports', lambda files, top, **_: PICO_LIKE[:-1])
    with pytest.raises(ValueError, match='lacks ports: rvfi_mem_wdata'):
        make(verilog_core)
    with pytest.raises(ValueError, match='contain the reset PC'):
        make(verilog_core, reset_pc='0x10')


def test_spinal_top_needs_explicit_bus(tmp_path):
    root = tmp_path / 'score'
    root.mkdir()
    (root / 'build.sbt').write_text('lazy val cpu = (project in file("."))\n')
    with pytest.raises(ValueError, match='--bus'):
        mapped.mapped_scaffold(root, isa='rv32i', top='demo.Top', reset_pc='0x80000000')
    result = mapped.mapped_scaffold(root, isa='rv32i', top='demo.Top', reset_pc='0x80000000', buses=[
        'i:req-rsp:cmd_valid=iBus_cmd_valid,cmd_ready=iBus_cmd_ready,address=iBus_cmd_payload_pc,'
        'rsp_valid=iBus_rsp_valid,rdata=iBus_rsp_payload_inst'], dry_run=True)
    assert 'ProjectRef(coreSource, "cpu")' in result['files']['rvw/build.sbt']
    assert 'rvw/templates/RvfiPort.scala' in result['files']
    assert 'Probe.retire' in result['files']['rvw/templates/CoreProbes.scala']
    assert 'ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb")' in result['files']['rvw/build.sbt']
    assert json.loads(result['files']['rvw/core-map.json'])['top'] == {'kind': 'spinal', 'class': 'demo.Top'}
    assert not (root / 'rvw').exists()


def test_cli_mapped_mode_requires_reset_pc(verilog_core, capsys):
    code = main(['init', str(verilog_core), '--isa', 'rv32i', '--verilog-top', 'core',
                 '--verilog', str(verilog_core / 'core.v'), '--json'])
    assert code == 2
    assert 'reset-pc' in json.loads(capsys.readouterr().out)['error']



def test_spinal_mapping_refuses_incompatible_scala(tmp_path):
    (tmp_path / 'build.sbt').write_text('ThisBuild / scalaVersion := "2.12.18"\nlazy val cpu = project\n')
    with pytest.raises(ValueError, match='Scala 2.13.14'):
        mapped.mapped_scaffold(tmp_path, isa='rv32i', top='demo.Top', sbt_project='cpu',
                               reset_pc='0x80000000', buses=[
            'm:valid-ready:valid=v,ready=r,address=a,rdata=d'])
    assert not (tmp_path / 'rvw').exists()


def test_query_preserves_external_source_and_simulation_options(verilog_core, tmp_path):
    source = tmp_path / 'external core.sv'
    source.write_text('module core(input clk); endmodule\n')
    make(verilog_core, verilog=[source], defines=['RISCV_FORMAL'], params=['WIDTH=32'])
    script = (verilog_core / 'rvw/build-db.sh').read_text()
    assert "--frontend slang --define RISCV_FORMAL --param WIDTH=32" in script
    assert str(source) in script
    assert '"$here/"' + str(source) not in script


def test_query_sizes_unsigned_parameter(verilog_core):
    import shlex
    result = make(verilog_core, params=['RESET_PC=0x80000000'])
    script = result['files']['rvw/build-db.sh'].replace('\\\n', ' ')
    assert "RESET_PC=32'h80000000" in shlex.split(script)


def test_mapped_adapter_has_a_runtime_source(verilog_core):
    result = make(verilog_core)
    source = verilog_core / 'rvw/src/main/scala/RvwMappedRuntime.scala'
    assert source.is_file()
    assert 'object RvwMappedRuntime' in source.read_text()
    assert str(source.relative_to(verilog_core)) in result['files']
