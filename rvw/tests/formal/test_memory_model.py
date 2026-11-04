from argparse import Namespace
import json
import shutil
import sys

import pytest
from rvw.common.proc import run_group
from rvw.formal.flows import memory_commands


def test_array_refuses_bit_level_engines():
    for engine in ['abc:pdr', 'smtbmc:yices,abc:bmc3', 'aiger:avy', 'btor:pono']:
        with pytest.raises(ValueError, match='smtbmc-only'):
            memory_commands(Namespace(memory_model='array', engine=engine))
    assert memory_commands(Namespace(memory_model='array', engine='smtbmc:yices,smtbmc:z3')) == ''
    assert memory_commands(Namespace(memory_model='map', engine='abc:pdr')) == 'memory_map -formal'


@pytest.mark.parametrize('encoding', ['array', 'map'])
@pytest.mark.parametrize('bad', [False, True])
def test_native_memory_preserves_read_write_semantics(tmp_path, encoding, bad):
    if not all(shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2')):
        pytest.skip('optional native formal tools missing')
    source = tmp_path / 'ram.sv'
    source.write_text('''module ram(input clk, input [3:0] addr, input [7:0] data, input we);
reg [7:0] mem [0:15];
reg valid=0;
reg [3:0] saved_addr;
reg [7:0] saved_data;
always @(posedge clk) begin
  valid <= we;
  if (we) begin mem[addr] <= data; saved_addr<=addr; saved_data<=data; end
  if (valid) assert(mem[saved_addr] == ''' + ('~saved_data' if bad else 'saved_data') + ''');
end
endmodule
''')
    out = tmp_path / 'out'
    proc = run_group([sys.executable, '-m', 'rvw', 'formal', 'bmc', '--verilog', str(source),
                      '--top', 'ram', '--memory-model', encoding, '--depth', '5',
                      '--timeout', '15', '--out', str(out)], capture=True, timeout=30)
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == ('fail' if bad else 'pass'), (result, proc.stdout, proc.stderr)
    assert proc.returncode == int(bad)
    assert result['memory_model']['retained_memory_cells'] == (1 if encoding == 'array' else 0)
    if encoding == 'array':
        smt = (out / 'sby/model/design_smt2.smt2').read_text()
        assert '(Array ' in smt
