import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from rvw.formal import rtl_refine
from rvw.formal.relations import candidates


def test_select_internal_memory_and_state():
    m = {'ports': {'clk': {'bits': [1]}, 'out': {'bits': [5]}},
         'netnames': {'clk': {'bits': [1]}, 'ram_data': {'bits': [2, 3]}, 'counter': {'bits': [4]},
                      'out': {'bits': [5]}},
         'cells': {'mem': {'type': '$mem_v2', 'connections': {'RD_DATA': [2, 3]}},
                   'reg': {'type': '$dff', 'connections': {'Q': [4]}},
                   'port_reg': {'type': '$dff', 'connections': {'Q': [5]}}}}
    assert rtl_refine.select_cuts(m) == [{'signal': 'ram_data', 'width': 2, 'kind': 'memory-read'},
                                       {'signal': 'counter', 'width': 1, 'kind': 'state'}]


def test_refines_to_concrete_proof(tmp_path, monkeypatch):
    src = tmp_path / 'dut.sv'
    src.write_text('module top(input clk); endmodule')
    plan = {'top': 'top', 'sources': [{'path': 'dut.sv', 'sha256': hashlib.sha256(src.read_bytes()).hexdigest()}]}
    def process(cmd, **kwargs):
        if cmd[0] == 'yosys':
            m = {'ports': {}, 'netnames': {'count': {'bits': [1]}},
                 'cells': {'ff': {'type': '$dff', 'connections': {'Q': [1]}}}}
            (Path(kwargs['cwd']) / 'inspect.json').write_text(json.dumps({'modules': {'top': m}}))
        else:
            out = Path(cmd[cmd.index('--out') + 1])
            out.mkdir()
            cut = '--cut' in cmd
            data = {'status': 'unknown' if cut else 'pass', 'proof_kind': 'unbounded', 'abstraction_counterexample': cut}
            (out / 'result.json').write_text(json.dumps(data))
        return SimpleNamespace(stdout='', stderr='', returncode=0, timed_out=False)
    monkeypatch.setattr(rtl_refine, 'run_group', process)
    r = rtl_refine.refine(plan, tmp_path, tmp_path / 'out')
    assert r['status'] == 'pass' and len(r['rounds']) == 2
    assert r['rounds'][0]['status'] == 'inconclusive'
    assert r['rounds'][1]['cuts'] == []


def test_relations_are_candidates():
    r = candidates({'a': 3, 'b': 3}, [{'a': 1, 'b': 2}, {'a': 2, 'b': 3}])
    assert r['rel_a_b_le'] == '(a <= b)'
    assert r['rel_a_b_offset'] == '(b == (a + 1))'
    assert 'rel_a_b_eq' not in r
