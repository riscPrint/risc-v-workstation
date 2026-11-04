"""Native Icarus adapter for the small RTL slice. Run from the captured tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from rvw.common.proc import run_group

request, output = map(Path, sys.argv[1:3])
case = json.loads(request.read_text())
root = Path(__file__).resolve().parent
work = request.with_suffix('')
work.mkdir()
# The experiment selects a seed via a separate public register x4.
seed = case['registers'].get('4', 0)
params = [int(seed == i) for i in range(1, 5)]
secret = case['registers']['1']
public = case['registers']['2']
source = root/'slice.v'
tb = work/'tb.v'
tb.write_text(f'''module tb;
reg clk=0, reset=1;
wire [31:0] pc, result, insn, protected_trace, test_output;
wire [4:0] rd; wire [3:0] cache; wire retire;
slice #({','.join(map(str,params))}) dut(clk,reset,32'd{secret},32'd{public},pc,result,retire,insn,rd,cache,protected_trace,test_output);
integer cycle=0; reg [31:0] oldpc;
always #5 clk=~clk;
initial begin
 @(negedge clk); reset=0;
 repeat(8) begin
   oldpc=pc; @(posedge clk); #1; cycle=cycle+1;
   if(retire) $display("R %h %h %d %h %d", oldpc,insn,rd,result,cycle);
   if(pc==32'h8000000c) begin
     $display("O %h %h %h",cache,protected_trace,test_output); $finish;
   end
   @(negedge clk);
 end
 $fatal(1,"no completion");
end
endmodule
''')

def tool(name):
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f'{name} not installed')
    return found

iverilog, vvp = tool('iverilog'), tool('vvp')
tool_hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (iverilog,vvp)}
binary = work/'sim'
for argv in ([iverilog, '-g2012', '-s', 'tb', '-o', str(binary), str(source), str(tb)], [vvp, str(binary)]):
    run = run_group(argv, capture=True, timeout=20)
    if run.returncode or run.timed_out:
        raise RuntimeError(run.stderr or run.stdout)
effects, cycles, observations = [], [], None
for line in run.stdout.splitlines():
    words = line.split()
    if words[0] == 'R':
        effects.append(dict(pc=int(words[1],16), insn=int(words[2],16), rd=int(words[3]),
                            rd_wdata=int(words[4],16), mem_addr=0, mem_rmask=0, mem_wmask=0, mem_wdata=0))
        cycles.append(int(words[5]))
    if words[0] == 'O':
        observations = dict(zip(('cache','protected_trace','test_output'), [int(x,16) for x in words[1:]]))
if any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h for p,h in tool_hashes.items()):
    raise RuntimeError('simulator changed during run')
output.write_text(json.dumps({'complete': observations is not None and len(effects)==2,
    'effects': effects, 'cycles': cycles, 'observations': observations,
    'tools': tool_hashes,
    'rtl_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
