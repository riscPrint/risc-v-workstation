from hashlib import sha256
import json
import shutil
import pytest
from rvw.formal.cover_hunt import run


@pytest.mark.parametrize('engine', ['smtbmc:yices', 'aiger:rIC3'])
def test_native_deeper_cover_witness_is_not_a_bug_or_safety_proof(tmp_path, engine):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2' if engine == 'smtbmc:yices' else 'rIC3')):
        pytest.skip('optional native cover-search tools missing')
    source = tmp_path / 'model.sv'
    source.write_text('''module top(input clk);
reg [3:0] count=0;
always @(posedge clk) begin count<=count+1;
assert(0);
cover(count==12);
cover(count==16);
end
endmodule''')
    plan = {'top': 'top', 'sources': [{'path': source.name, 'sha256': sha256(source.read_bytes()).hexdigest()}],
            'depths': [4, 20], 'engines': [engine], 'seeds': [0, 1]}
    out = tmp_path / 'out'
    r = run(plan, tmp_path, out, budget=30, timeout=6)
    (out / 'result.json').write_text(json.dumps(r, indent=2))
    assert r['status'] == 'inconclusive' and r['covered'] == 1, r
    hit = next(t for t in r['targets'] if t['status'] == 'covered')
    assert hit['proof_kind'] == 'bounded_reachability'
    assert [a['depth'] for a in hit['attempts']] == ([4, 20] if engine == 'smtbmc:yices' else [4, 4, 20])
    assert all(a['status'] == 'inconclusive' for a in hit['attempts'][:-1])
    assert hit['attempts'][-1]['status'] == 'fail'
    miss = next(t for t in r['targets'] if t['status'] != 'covered')
    assert miss['status'] == 'inconclusive' and miss['proof_kind'] == 'none'
    assert not r['unstarted']
