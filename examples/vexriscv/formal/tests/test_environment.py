"""Check the shipped bus assumptions against an independent transaction monitor."""
from pathlib import Path
import shutil

import pytest

from rvw.common.proc import run_group


@pytest.mark.parametrize('mode,quiet_reset', [('bmc', False), ('bmc', True), ('cover', False)])
def test_bus_environment(tmp_path, mode, quiet_reset):
    if not all(shutil.which(tool) for tool in ('sby', 'yosys', 'bitwuzla')):
        pytest.skip('native formal tools required')
    wrapper = (Path(__file__).parents[1] / 'wrapper.sv.in').read_text()
    environment = wrapper[wrapper.index('`ifdef VEXRISCV_FAIRNESS'):wrapper.rindex('endmodule')]
    # Exercise the actual shipped environment without the core. Inputs are arbitrary.
    source = '''module test(input clock);
reg [4:0] cycle = 0;
always @(posedge clock) if (cycle < 20) cycle <= cycle + 1;
wire reset = cycle == 0;
(* anyseq *) reg iBus_cmd_valid, iBus_cmd_ready, iBus_rsp_ready;
(* anyseq *) reg dBus_cmd_valid, dBus_cmd_ready, dBus_rsp_ready, dBus_cmd_payload_wr;
wire rvfi_trap = 0;
'''
    if quiet_reset:
        # Isolate post-reset accounting from the separate reset response check.
        source += 'always @(posedge clock) if (reset) assume (!iBus_rsp_ready && !dBus_rsp_ready);\n'
    monitor = '''
integer fetches = 0, loads = 0;
reg overlapped = 0, replaced = 0, stored = 0;
reg [2:0] iw = 0, dw = 0, ic = 0, dc = 0;
always @(posedge clock) begin
  if (reset) begin
    assert (!iBus_rsp_ready && !dBus_rsp_ready);
    fetches <= 0; loads <= 0;
    iw <= 0; dw <= 0; ic <= 0; dc <= 0;
  end else begin
    assert (!iBus_rsp_ready || fetches > 0);
    assert (!dBus_rsp_ready || loads > 0);
    fetches <= fetches + (iBus_cmd_valid && iBus_cmd_ready) - iBus_rsp_ready;
    loads <= loads + (dBus_cmd_valid && dBus_cmd_ready && !dBus_cmd_payload_wr) - dBus_rsp_ready;
    iw <= (fetches > 0 && !iBus_rsp_ready) ? iw + 1 : 0;
    dw <= (loads > 0 && !dBus_rsp_ready) ? dw + 1 : 0;
    ic <= (iBus_cmd_valid && !iBus_cmd_ready) ? ic + 1 : 0;
    dc <= (dBus_cmd_valid && !dBus_cmd_ready) ? dc + 1 : 0;
    assert (iw < 4 && dw < 4 && ic < 4 && dc < 4);
    if (fetches >= 2) overlapped <= 1;
    if (fetches > 0 && iBus_rsp_ready && iBus_cmd_valid && iBus_cmd_ready &&
        loads > 0 && dBus_rsp_ready && dBus_cmd_valid && dBus_cmd_ready && !dBus_cmd_payload_wr)
      replaced <= 1;
    if (dBus_cmd_valid && dBus_cmd_ready && dBus_cmd_payload_wr) stored <= 1;
    cover (overlapped && replaced && stored && fetches == 0 && loads == 0 && cycle > 10);
    cover (fetches > 0 && dBus_cmd_payload_wr && iBus_rsp_ready);
  end
end
endmodule
'''
    (tmp_path / 'test.sv').write_text(source + environment + monitor)
    (tmp_path / 'test.sby').write_text(f'''[options]
mode {mode}
depth 20
[engines]
smtbmc bitwuzla
[script]
read -formal -D VEXRISCV_FAIRNESS test.sv
prep -top test
[files]
test.sv
''')
    with (tmp_path / 'run.log').open('w') as log:
        result = run_group(['sby', '-f', 'test.sby'], cwd=tmp_path, timeout=60, stdout=log, stderr=log)
    assert not result.timed_out, (tmp_path / 'run.log').read_text()
    assert result.returncode == 0, (tmp_path / 'run.log').read_text()
    assert (tmp_path / 'test/status').read_text().split()[0] == 'PASS'
