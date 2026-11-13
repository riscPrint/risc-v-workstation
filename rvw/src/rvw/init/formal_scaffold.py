import json
import os

def formal(core):
    """Single-outstanding req/rsp environment with stable byte memory."""
    if core['top']['kind'] != 'spinal' or core['xlen'] != 32 or not core['rvfi'] or core['isa'] not in ('rv32i', 'rv32im'):
        return {}, ''
    if len(core['buses']) != 1 or core['buses'][0]['protocol'] != 'req-rsp':
        return {}, ''
    bus = core['buses'][0]; pins=bus['signals']; top=core['top']
    if top.get('reset_active','high') != 'high' or 'rsp_ready' in pins:
        return {}, ''
    from rvw.formal.riscv import FIELDS
    prefix=core['rvfi']['prefix']
    fields=list(FIELDS)
    # ixl is optional on the mapped retirement declaration. The ISA fixes it here.
    con={top.get('clock','clk'):'clock', top.get('reset','reset'):'reset'}
    con.update({prefix+f:'rvfi_'+f for f in fields if f!='ixl'})
    con.update({v:'0' for v in core['constants']})
    con.update({v:'0' for v in core.get('irq',{}).values()})
    signals=dict(cmd_valid='req',cmd_ready="1'b1",address='address',write='write_enable',
                 wdata='write_data',mask='write_mask',rsp_valid='response_valid',rdata='response_data',error="1'b0")
    con.update({v:signals[k] for k,v in pins.items()})
    read_mask="{4{req && !write_enable}}"
    write_mask="(req && write_enable) ? write_mask : 4'b0"
    text='''module rvfi_wrapper(input clock, input reset, `RVFI_OUTPUTS);
wire req, write_enable;
wire [31:0] address, write_data;
wire [3:0] write_mask;
(* anyseq *) reg [31:0] read_data;
reg response_valid = 0;
reg [31:0] response_data;
wire [3:0] read_mask = READ_MASK;
wire [3:0] store_mask = WRITE_MASK;
assign rvfi_ixl = 2'd1;
always @(posedge clock) begin
 if (reset) response_valid <= 0;
 else begin
  response_valid <= req && RESPONSE;
  response_data <= read_data;
 end
end
@MEMORY_ENVIRONMENT@
TOP dut(@DUT_CONNECTIONS@);
// Port map used by riscv-formal: @RVFI_CONNECTIONS@
endmodule
'''.replace('READ_MASK',read_mask).replace('WRITE_MASK',write_mask).replace('RESPONSE',"1'b1" if bus['write_response'] else '!write_enable')
    text=text.replace('TOP', top.get('module',top.get('class','').split('.')[-1]))
    text=text.replace('@DUT_CONNECTIONS@', ',\n'.join(f'.{k}({v})' for k,v in con.items()))
    # Keep the marker on one comment line: prepare expands it into multiple lines.
    text=text.replace('// Port map used by riscv-formal: @RVFI_CONNECTIONS@', '/* @RVFI_CONNECTIONS@ */')
    cfg='''
[riscv_formal]
root = FORMAL_ROOT
wrapper = "rvw/formal/wrapper.sv"
verilog = ["rvw/out/export/core.v"]
build = ["./rvw/export-rtl.sh"]
isa = ISA
nret = 1
checks = ["insn_add_ch0", "insn_lw_ch0", "insn_sw_ch0", "cover"]
# Run smoke with --rvfi-trace, then pass --trace to rvw formal isa.
# Or set depth explicitly after review.
solver = "yices"
[riscv_formal.ports]
PORTS
[riscv_formal.memory]
protocol = "combinational-byte"
initial = "symbolic-stable"
response_cycles = 0
address_width = 32
reads = [{address="address",data="read_data",mask="read_mask"}]
writes = [{address="address",data="write_data",mask="store_mask"}]
'''.replace('FORMAL_ROOT',json.dumps(os.environ.get('RISCV_FORMAL','~/.cache/rvw/riscv-formal'))).replace('ISA',json.dumps(core['isa'])).replace('PORTS','\n'.join(f'{f} = "{prefix+f}"' for f in fields))
    defaults = {'write': "assign write_enable = 1'b0;", 'wdata': "assign write_data = 32'b0;", 'mask': "assign write_mask = 4'b0;"}
    text = text.replace('@MEMORY_ENVIRONMENT@', '\n'.join(v for k,v in defaults.items() if k not in pins) + '\n@MEMORY_ENVIRONMENT@')
    return {'rvw/formal/wrapper.sv':text}, cfg
