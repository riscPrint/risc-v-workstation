"""The SV project entry can select the working mapped adapter explicitly."""
import json
import pytest
from rvw.cli import main
from rvw.init import mapped
from test_init_mapped import PICO_LIKE

pytestmark = pytest.mark.fast


def test_sv_reset_pc_selects_mapped_adapter(tmp_path, monkeypatch, capsys):
    (tmp_path/'core.sv').write_text('module core(input clk); endmodule\n')
    monkeypatch.setattr(mapped, 'verilog_ports', lambda *a, **kw: PICO_LIKE)
    code = main(['init', str(tmp_path), '--hdl', 'sv', '--top', 'core', '--source', str(tmp_path/'core.sv'),
                 '--isa', 'rv32i', '--reset-pc', '0x80000000', '--reset', 'resetn',
                 '--reset-active', 'low', '--accept-platform-defaults', '--json'])
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result['mapped'] is True
    mapping = json.loads((tmp_path/'rvw/core-map.json').read_text())
    assert mapping['top']['module'] == 'core' and mapping['rvfi']['prefix'] == 'rvfi_'
    assert 'MappedMain' in (tmp_path/'rvw/run.sh').read_text()


def test_sv_mapped_refuses_ignored_include(tmp_path, capsys):
    code = main(['init', str(tmp_path), '--hdl', 'sv', '--top', 'core', '--isa', 'rv32i',
                 '--reset-pc', '0x80000000', '-I', 'include', '--json'])
    assert code == 2
    assert 'does not yet support -I' in json.loads(capsys.readouterr().out)['error']
