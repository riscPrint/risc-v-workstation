import pytest

def test_native_global_consistency_and_concrete_validation(tmp_path):
    import hashlib
    import json
    import shutil
    from rvw.formal.uf_prove import prove
    if not all(shutil.which(t) for t in ['yosys', 'sby', 'yices-smt2']):
        pytest.skip('optional native SMTBMC/Yices missing')
    pipeline = 'module top(input clk,input[3:0] a,b); reg[3:0] olda,oldb; reg[7:0] product; reg valid=0; always @(posedge clk) begin olda<=a;oldb<=b;product<=a*b;valid<=1; if(valid) assert(product==olda*oldb);end endmodule'
    for name, text in [('pipeline', pipeline), ('fault', pipeline.replace('product<=a*b', 'product<=a*b+1'))]:
        source = tmp_path / (name + '.sv')
        source.write_text(text)
        plan = {'top': 'top', 'sources': [{'path': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}
        r = prove(plan, tmp_path, tmp_path / (name + '-uf'), timeout=12)
        assert r['smt_models']
        if name == 'pipeline':
            assert r['status'] == 'pass' and r['proof_kind'] == 'unbounded_uf_overapproximation', r
            assert r['rewritten_operations'] == 2
        else:
            assert r['status'] == 'inconclusive', r
            concrete = prove({**plan, 'operators': []}, tmp_path, tmp_path / 'concrete', timeout=12)
            assert concrete['status'] == 'fail' and concrete['proof_kind'] == 'counterexample', concrete
