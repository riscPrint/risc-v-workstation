from hashlib import sha256
import json
import shutil
import pytest
from rvw.formal.ic3_lemmas import run


def test_native_export_related_property_revision_and_refused_stale_cone(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'yosys-abc', 'sby', 'yices-smt2')):
        pytest.skip('optional native formal tools missing')
    base = 'module top(input clk,input enable); reg [1:0] count=0; always @(posedge clk) begin if(enable) count<=count==2 ? 0 : count+1; assert(count!=3); end endmodule'
    def prove(name, text, library=None):
        source = tmp_path / (name + '.sv')
        source.write_text(text)
        plan = {'top': 'top', 'sources': [{'path': source.name, 'sha256': sha256(source.read_bytes()).hexdigest()}]}
        out = tmp_path / name
        r = run(plan, tmp_path, out, library=library, timeout=12)
        (out / 'result.json').write_text(json.dumps(r, indent=2))
        return r
    exported = prove('export', base)
    assert exported['status'] == 'pass' and len(exported['entries']) == 1, exported
    library = tmp_path / 'export/library.json'
    related = base.replace('assert(count!=3)', 'assert(!(count[1] && count[0]))')
    reused = prove('related', related, library)
    assert reused['status'] == 'pass' and len(reused['entries']) == 1, reused
    revised = related.replace('input enable)', 'input enable, output reg [7:0] unrelated=0)').replace('begin if(enable)', 'begin unrelated<=unrelated+1; if(enable)')
    reused = prove('revision', revised, library)
    assert reused['status'] == 'pass' and len(reused['entries']) == 1, reused
    fault = prove('fault', base.replace('count==2', 'count==3'), library)
    assert fault['status'] == 'fail' and not fault['entries'], fault
    assert fault['rejected'][0]['reason'] == 'cone_or_certification_mismatch'
    conditional = prove('conditional', base.replace('assert(count!=3)', 'assume(enable); assert(count!=3)'))
    assert conditional['status'] == 'inconclusive' and conditional['reason'] == 'source_assumptions_unsupported'
