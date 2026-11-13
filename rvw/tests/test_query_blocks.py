"""SpinalBlocks diagrams from HDL design databases (`rvw query export blocks`)."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from rvw.cli import main
from rvw.query.hdl import build_hdl

YOSYS, NODE = shutil.which('yosys'), shutil.which('node')
ENGINE = Path(__file__).parents[2] / 'SpinalBlocks/engine'
SV = '''module leaf(input clk, input [7:0] d, input en, output [7:0] q);
reg [7:0] r;
always @(posedge clk) if (en) r <= d;
assign q = r;
endmodule
module top(input clk, input [7:0] a, input en, input [1:0] sel, output [7:0] y, output [7:0] z);
wire [7:0] mid;
leaf u0(clk, a, en, mid);
leaf u1(clk, mid, en, y);
reg [7:0] m [0:3];
always @(posedge clk) m[sel] <= a;
assign z = m[sel];
endmodule
'''
CHECK = '''import { readFileSync } from 'node:fs';
const [, , engine, file] = process.argv;
const core = await import(engine + '/src/core.ts');
const design = await core.loadDesign(new Uint8Array(readFileSync(file)));
const state = core.initialView();
let blocks = 0;
for (const name of Object.keys(design.modules))
  blocks += core.buildViewGraph(design, name, core.moduleView(state, name), state.options).blocks.length;
console.log(JSON.stringify({ modules: Object.keys(design.modules).length, blocks }));
'''


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_blocks_from_hdl(tmp_path, capsys):
    source = tmp_path / 'top.sv'
    source.write_text(SV)
    db = tmp_path / 'top.db'
    build_hdl([source], 'top', db, yosys=YOSYS)
    out = tmp_path / 'blocks.json.gz'
    assert main(['query', 'export', 'blocks', str(out), '--db', str(db), '--json']) == 0
    capsys.readouterr()
    d = json.loads(gzip.decompress(out.read_bytes()))
    assert d['format'] == 'spinalblocks' and d['version'] == 1 and d['top'] == 'top'
    top, leaf = d['modules']['top'], d['modules']['leaf']
    assert leaf['instanceCount'] == 2 and [i['name'] for i in top['instances']] == ['u0', 'u1']
    assert {n['id'] for n in top['nodes']} == {'mem:m'} and {n['id'] for n in leaf['nodes']} == {'sig:r'}

    def nets(m):
        def end(e):
            return e.get('port') if e['kind'] == 'port' else e['id'] + ('.' + e['port'] if 'port' in e else '')
        return {(end(n['from']), end(t)): n for n in m['nets'] for t in n['to']}
    t = nets(top)
    assert ('a', 'inst:u0.d') in t and ('inst:u0.q', 'inst:u1.d') in t and ('inst:u1.q', 'y') in t
    assert ('a', 'mem:m') in t and ('mem:m', 'z') in t and t[('sel', 'mem:m')]['control']
    assert ('a', 'y') not in t  # through instances, not around them
    lf = nets(leaf)
    assert set(lf) == {('d', 'sig:r'), ('en', 'sig:r'), ('sig:r', 'q')} and lf[('en', 'sig:r')]['control']
    for m in d['modules'].values():
        assert all(n['from'] != x for n in m['nets'] for x in n['to'])
    if NODE:
        script = tmp_path / 'check.mjs'
        script.write_text(CHECK)
        r = subprocess.run([NODE, str(script), str(ENGINE), str(out)], capture_output=True, text=True, timeout=60)
        if 'ERR_UNKNOWN_FILE_EXTENSION' in r.stderr:
            pytest.skip('node cannot load TypeScript sources')
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout) == {'modules': 2, 'blocks': 4}  # u0, u1, m; r
