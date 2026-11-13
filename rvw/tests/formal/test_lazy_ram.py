from rvw.formal.lazy_ram import abstract_words, observed_addresses
import pytest


def design():
    return {'modules': {'top': {'ports': {}, 'netnames': {
        'mem[0]': {'bits': [2, 3], 'attributes': {'init': '00'}},
        'mem[1]': {'bits': [4, 5], 'attributes': {'init': '11'}}}, 'cells': {
        'w0': {'type': '$dff', 'connections': {'Q': [2, 3], 'D': [6, 7]}},
        'w1': {'type': '$dff', 'connections': {'Q': [4, 5], 'D': [8, 9]}}}}}}


def test_unwatched_words_are_uninitialized_inputs_watched_dynamics_stay():
    d = design()
    r = abstract_words(d, 'top', {0: 'mem[0]', 1: 'mem[1]'}, {1})['modules']['top']
    assert 'w0' not in r['cells']
    assert r['ports']['rvw_ram_word_0'] == {'direction': 'input', 'bits': [2, 3]}
    assert 'init' not in r['netnames']['mem[0]']['attributes']
    assert r['cells']['w1'] == d['modules']['top']['cells']['w1']
    assert r['netnames']['mem[1]']['attributes']['init'] == '11'
    assert abstract_words(d, 'top', {0: 'mem[0]', 1: 'mem[1]'}, {0, 1}) == d
    assert 'w0' in d['modules']['top']['cells']


def test_ambiguous_driver_fails_closed():
    d = design()
    d['modules']['top']['cells']['alias'] = d['modules']['top']['cells']['w0']
    with pytest.raises(ValueError, match='one whole-word'):
        abstract_words(d, 'top', {0: 'mem[0]'}, set())


def test_trace_addresses_only_prioritize_refinement(tmp_path):
    trace = tmp_path / 'trace.vcd'
    trace.write_text('$var wire 4 ! addr $end\n$var wire 4 ? other $end\n'
                     'b0011 !\nbxxxx !\nb0010 ?\nb1010 !\n')
    assert observed_addresses(tmp_path, {'addr'}) == {3, 10}


def test_native_masked_memory_retains_only_addressed_word(tmp_path):
    import hashlib
    import json
    import shutil
    from pathlib import Path
    from rvw.formal.lazy_ram import run
    if not all(shutil.which(t) for t in ['yosys', 'sby', 'yosys-abc']):
        pytest.skip('optional native formal tools missing')
    source = tmp_path / 'ram.sv'
    source.write_text('''module top(input clk, input [1:0] addr, input [3:0] mask, data);
reg [3:0] mem [0:3]; reg [3:0] shadow=1; integer i;
initial for(i=0;i<4;i=i+1) mem[i]=1;
always @(posedge clk) begin
  if(mask[0]) begin mem[addr][0]<=data[0]; if(addr==1) shadow[0]<=data[0]; end
  if(mask[1]) begin mem[addr][1]<=data[1]; if(addr==1) shadow[1]<=data[1]; end
  if(mask[2]) begin mem[addr][2]<=data[2]; if(addr==1) shadow[2]<=data[2]; end
  if(mask[3]) begin mem[addr][3]<=data[3]; if(addr==1) shadow[3]<=data[3]; end
end
always @* assert(mem[1] == shadow);
endmodule''')
    plan = {'top': 'top', 'memory': 'mem', 'sources': [{'path': source.name,
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}
    result = run(plan, tmp_path, tmp_path / 'out', budget=25, timeout=8)
    assert result['status'] == 'pass', result
    assert result['watched'] == [1]
    assert result['rounds'][-1]['memory_state_bits'] == 4
    assert result['rounds'][0]['status'] == 'inconclusive'


def test_aliased_words_cannot_remove_a_watched_driver():
    d = design()
    d['modules']['top']['netnames']['mem[1]']['bits'] = [2, 3]
    with pytest.raises(ValueError, match='distinct nonconstant'):
        abstract_words(d, 'top', {0: 'mem[0]', 1: 'mem[1]'}, {1})
