"""Project-bound RTL pin capture and independent architectural comparisons."""
import json
from pathlib import Path
import shutil

import pytest

from rvw.soc.observer import SIGNALS,digest,generate,pack


def binding(tmp_path):
    data=dict(schema='rvw.soc-observer/1',data_bytes=4,
              signals={name:'bench.'+name for name in SIGNALS})
    path=tmp_path/'binding.json';path.write_text(json.dumps(data));return path


def architectural(tmp_path,schedule,rtl_hash='rtl-fixture'):
    from rvw.cosim.trace import record
    rows=[dict(schema='rvw.rvfi/1',xlen=32,isa='rv32i',core='bridge-fixture',config='unit',elf='fixture.elf')]
    for sample in schedule:
        order=sample['order'];load=order==1
        effect=dict(pc=0x1000+4*order,pc_next=0x1004+4*order,insn=0x0000a183 if load else 0x0020a023,
                    mode=3,rd=3 if load else 0,rd_wdata=0x44332211 if load else 0,
                    mem_addr=0x1000,mem_rmask=15 if load else 0,mem_wmask=0 if load else 15,
                    mem_rdata=0x44332211 if load else 0,mem_wdata=0 if load else 0x44332211,
                    trap=False,mem_fault=False,before=[0,0x1000,0x44332211]+[0]*29)
        rows.append(record(effect,order,cycle=sample['cycle'],xlen=32))
    rows.append(dict(event='end',cycle=schedule[-1]['cycle']+1,status='pass'))
    trace=tmp_path/'trace.jsonl';trace.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
    run=dict(source={'rev':'bridge-fixture'},rtl_sha256=rtl_hash,elf_sha256='elf-fixture',seed=9,
             details={'simulation_session':{'run_id':'observer-test'}})
    path=tmp_path/'run.json';path.write_text(json.dumps(run));return trace,path


@pytest.mark.fast
def test_generate_read_only_handshakes_and_required_tags(tmp_path):
    path=binding(tmp_path);report=generate(path,tmp_path/'generated')
    text=(tmp_path/'generated/observer.sv').read_text()
    assert report['status']=='generated'
    assert 'bench.request_valid && bench.request_ready' in text
    assert 'bench.response_valid && bench.response_ready' in text
    assert 'bench.retire_tag' in text and 'bench.retire_count !== 1' in text
    assert report['monitor_sha256']==digest(tmp_path/'generated/observer.sv')
    data=json.loads(path.read_text());del data['signals']['retire_tag'];path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='every observer signal'):
        generate(path,tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()


@pytest.mark.fast
def test_pack_identity_gaps_and_no_clobber(tmp_path):
    path=binding(tmp_path)
    trace,run=architectural(tmp_path,[dict(order=0,cycle=5),dict(order=1,cycle=9)])
    header=dict(schema='rvw.soc-observed-pins/1',binding_sha256=digest(path),run_id='observer-test',
                rtl_sha256='rtl-fixture',elf_sha256='elf-fixture',seed=9)
    pins=tmp_path/'pins.jsonl';pins.write_text(json.dumps(header)+'\n')
    out=tmp_path/'events.jsonl'
    result=pack(path,pins,trace,run,out)
    assert result['status']=='inconclusive' and result['gaps'] and result['pairs']==0
    with pytest.raises(FileExistsError):pack(path,pins,trace,run,out)
    for field,value in [('run_id','other'),('binding_sha256','other'),('seed',True),('rtl_sha256','other')]:
        changed=dict(header,**{field:value});pins.write_text(json.dumps(changed)+'\n')
        with pytest.raises(ValueError):pack(path,pins,trace,run,tmp_path/'refused.jsonl')
        assert not (tmp_path/'refused.jsonl').exists()


@pytest.mark.fast
def test_cli_and_mcp_registration():
    from rvw.cli import build_parser
    args=build_parser().parse_args(['soc','observe','--binding','b','--out','o'])
    assert args.observe_action=='observe'
    from rvw.soc.commands.observe import mcp_tools
    assert [tool.name for tool in mcp_tools()]==['soc_observe','soc_observe_pack']


@pytest.mark.parametrize('bad',[False,True])
def test_native_bridge_pin_capture(tmp_path,bad):
    if any(not shutil.which(tool) for tool in ('iverilog','vvp')):
        pytest.skip('Icarus compiler and runtime required')
    from rvw.common.proc import run_group
    path=binding(tmp_path);generate(path,tmp_path/'generated')
    arch=tmp_path/'architectural.jsonl'
    rtl=tmp_path/'bridge.sv'
    rtl.write_text('''module bench;
reg clock=0; always #5 clock=~clock;
reg reset=1; integer cycle=0; always @(posedge clock) cycle<=cycle+1;
reg request_valid=0,request_ready=0,request_write=0;
reg [63:0] request_tag=0; reg [31:0] request_address=32'h1000,request_data=0;
reg [3:0] request_mask=15;
reg response_valid=0; wire response_ready=1; reg response_error=0;
reg [63:0] response_tag; reg [31:0] response_data;
reg retire_valid=0; reg [63:0] retire_order=0,retire_tag; wire [1:0] retire_count=1;
reg [31:0] memory=0; reg [63:0] next_order=0;
integer bad,arch_fd;
initial begin
 if (!$value$plusargs("BAD=%d",bad)) bad=0;
 arch_fd=$fopen('''+json.dumps(str(arch))+''',"w");
 repeat(2) @(negedge clock); reset=0;
 request_valid=1; request_write=1; request_tag=1; request_data=32'h44332211;
 repeat(2) @(negedge clock); request_ready=1;
 @(negedge clock); request_valid=0;
 repeat(4) @(negedge clock); request_valid=1; request_write=0; request_tag=2;
 @(negedge clock); request_valid=0;
 repeat(5) @(negedge clock); $fclose(arch_fd); $finish;
end
always @(posedge clock) if(!reset) begin
 response_valid<=0; retire_valid<=0;
 if(request_valid && request_ready) begin
  response_valid<=1; response_tag<=request_tag;
  if(request_write) begin memory<=request_data; response_data<=0; end
  else response_data<=memory ^ bad;
 end
 if(response_valid && response_ready) begin
  retire_valid<=1; retire_tag<=response_tag; retire_order<=next_order; next_order<=next_order+1;
 end
 // This retirement schedule is separate from the bus observer. Expected memory
 // effects come from the two-operation program in the Python architectural model.
 if(retire_valid) $fdisplay(arch_fd,"{\\"order\\":%0d,\\"cycle\\":%0d}",retire_order,cycle);
end
endmodule
''')
    binary=tmp_path/'bridge.vvp'
    with (tmp_path/'compile.log').open('w') as log:
        compiled=run_group(['iverilog','-g2012','-s','bench','-s','rvw_soc_observer','-o',str(binary),str(rtl),str(tmp_path/'generated/observer.sv')],
                           cwd=tmp_path,stdout=log,stderr=log,timeout=60)
    assert compiled.returncode==0,(tmp_path/'compile.log').read_text()
    pins=tmp_path/'pins.jsonl'
    args=['vvp',str(binary),'+RVW_SOC_EVENTS='+str(pins),'+RVW_RUN_ID=observer-test',
          '+RVW_RTL_SHA256='+digest(rtl),'+RVW_ELF_SHA256=elf-fixture','+RVW_SEED=9','+BAD='+str(int(bad))]
    with (tmp_path/'simulation.log').open('w') as log:
        simulation=run_group(args,cwd=tmp_path,stdout=log,stderr=log,timeout=60)
    assert simulation.returncode==0,(tmp_path/'simulation.log').read_text()
    schedule=[json.loads(line) for line in arch.read_text().splitlines()]
    assert [row['order'] for row in schedule]==[0,1]
    trace,run=architectural(tmp_path,schedule,rtl_hash=digest(rtl))
    result=pack(path,pins,trace,run,tmp_path/'events.jsonl')
    assert result['status']==('mismatch' if bad else 'inconclusive') and result['pairs']==2
    assert not result['gaps']
    from rvw.soc.pairing import check
    checked=check(tmp_path/'events.jsonl',trace,run)
    assert checked['status']==result['status']
    events=[json.loads(line) for line in pins.read_text().splitlines()[1:]]
    assert len([row for row in events if row['event']=='request'])==2
    if not bad:
        assert all(item['status']=='consistent' for pair in checked['pairs'] for item in pair['checks'])
    # Exercise CLI exit semantics through the same native capture.
    import sys
    with (tmp_path/'pack-cli.log').open('w') as log:
        cli=run_group([sys.executable,'-m','rvw','soc','observe-pack','--binding',str(path),
                       '--pins',str(pins),'--trace',str(trace),'--result',str(run),
                       '--out',str(tmp_path/'cli-events.jsonl'),'--json'],
                      cwd=tmp_path,stdout=log,stderr=log,timeout=30)
    assert cli.returncode==(1 if bad else 3),(tmp_path/'pack-cli.log').read_text()
    assert json.loads((tmp_path/'pack-cli.log').read_text())['status']==result['status']
