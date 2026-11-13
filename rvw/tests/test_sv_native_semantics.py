"""Semantic SV declarations and clock options. These tests do not prove a core."""
import json
import sqlite3
from pathlib import Path

import pytest

from lint_builder import Builder
from rvw.common.proc import Result
from rvw.formal.isa_activation import cover_source
from rvw.formal.riscv import FIELDS, run, validate
from rvw.formal.rvfi_binding import generate
from rvw.lint.rules import analyze
from rvw.query.db import run_on
from rvw.query.hdl import _Writer, schema_sql
from rvw.query.hdl_slang import automatic_locals

pytestmark = pytest.mark.fast


def test_automatic_local_scopes():
    auto = {'kind': 'Subroutine', 'name': 'f', 'defaultLifetime': 'Automatic',
            'members': [{'kind': 'FormalArgument', 'name': 'a'},
                        {'kind': 'Variable', 'name': 'v'},
                        {'kind': 'Variable', 'name': 's', 'lifetime': 'Static'}]}
    ast = {'members': [{'kind': 'Instance', 'body': {'members': [auto,
        {'kind': 'Instance', 'name': 'u', 'body': {'members': [auto]}},
        {'kind': 'GenerateBlockArray', 'name': 'g', 'members': [
            {'kind': 'GenerateBlock', 'constructIndex': 3, 'members': [auto]},
            {'kind': 'GenerateBlock', 'isUninstantiated': True, 'members': [auto]}]}]}}]}
    assert automatic_locals(ast) == {'f.a', 'f.v', 'u.f.a', 'u.f.v', 'g[3].f.a', 'g[3].f.v'}


def test_writer_marks_only_automatic_declarations():
    conn = sqlite3.connect(':memory:')
    conn.executescript(schema_sql())
    conn.execute("INSERT INTO components(id,path,name,depth) VALUES(1,'','top',0)")
    writer = _Writer(conn, {'modules': {}}, {}, automatic={'f.a'})
    writer.signal(1, 'f.a', 'a')
    writer.signal(1, 'floating', 'floating')
    tags = dict(conn.execute('SELECT path,tags FROM signals'))
    assert 'hdl:automatic-local' in tags['f.a'].split()
    assert 'hdl:automatic-local' not in tags['floating'].split()


def test_undriven_exception_needs_unused_automatic_local(tmp_path):
    b = Builder(tmp_path / 'db')
    b.sig('local', tags='hdl:automatic-local')
    b.sig('loaded_local', tags='hdl:automatic-local')
    b.sig('floating')
    b.sig('out', direction='out')
    b.assign('out', 'use', source='loaded_local')
    b.edge('loaded_local', 'out')
    report = run_on(b.done(), lambda d: analyze(d, {}))
    undriven = {f['endpoint'] for f in report['findings'] if f['rule'] == 'lint.undriven'}
    assert 'local' not in undriven
    assert {'loaded_local', 'floating'} <= undriven
    assert any(f['rule'] == 'lint.unused' and f['endpoint'] == 'local' for f in report['findings'])


@pytest.fixture
def config(tmp_path):
    root = tmp_path / 'upstream'
    for name in ('checks', 'insns'):
        (root / name).mkdir(parents=True)
    wrapper = tmp_path / 'wrapper.in'
    wrapper.write_text('@RVFI_CONNECTIONS@')
    rtl = tmp_path / 'rtl.v'
    rtl.write_text('module top; endmodule')
    return dict(root=str(root), wrapper=str(wrapper), verilog=[str(rtl)], isa='rv32imc',
                nret=1, depth=6, solver='bitwuzla', checks=['insn_add_ch0', 'cover'],
                ports={f: 'trace_' + f for f in FIELDS})


@pytest.mark.parametrize('enabled', [False, True])
def test_multiclock_job_and_activation(config, tmp_path, monkeypatch, enabled):
    config['multiclock'] = enabled
    def fake(argv, cwd, **kwargs):
        work = Path(cwd)
        if argv[0] != 'sby':
            (work / 'checks').mkdir()
            for name in config['checks']:
                (work / 'checks' / (name + '.sby')).write_text(
                    '[options]\nmode bmc\ndepth 6\n[engines]\nsmtbmc bitwuzla\n[script]\n')
        else:
            source = (work / argv[-1]).read_text()
            assert ('multiclock on' in source) is enabled
            assert ('multiclock on' in cover_source(source, 'bitwuzla')) is enabled
            dest = work / Path(argv[-1]).stem
            dest.mkdir()
            (dest / 'status').write_text('PASS')
        return Result(0)
    monkeypatch.setattr('rvw.formal.riscv.run_group', fake)
    assert run(config, tmp_path / 'run', 1, 'fixture').verdict == 'inconclusive'


@pytest.mark.parametrize('wrong', [0, 1, 'true', None])
def test_multiclock_requires_boolean(config, wrong):
    config['multiclock'] = wrong
    with pytest.raises(ValueError, match='multiclock'):
        validate(config)


def test_binding_forwards_multiclock(config, tmp_path):
    plan = dict(config, schema='rvw.rvfi-binding/1', top='Unit', clock='clk', reset='rst', multiclock=True)
    manifest = tmp_path / 'binding.json'
    manifest.write_text(json.dumps(plan))
    result = generate(manifest, tmp_path / 'generated')
    from rvw.common.project import load_project
    assert load_project(result['project']).sections['riscv_formal']['multiclock'] is True
