"""C8 named-boundary regressions for SpinalDB and query inputs."""
import base64
from contextlib import closing
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sqlite3
import os
import subprocess
import sys

import pytest

from race_injection import race_injector
from rvw.query.db import DesignDB
from rvw.query import ops

SPEC = importlib.util.spec_from_file_location('hdl_capture', Path(__file__).resolve().parents[2] /
                                             'SpinalDB/scripts/hdl_capture.py')
hdl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hdl)


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
@pytest.mark.parametrize('target', ['root', 'include', 'simulation'])
def test_hdl_consumes_only_captured_bytes(tmp_path, race_injector, replace, revert, target):
    body = tmp_path / 'Box.v'
    header = tmp_path / 'value.svh'
    simulation = tmp_path / 'simulation.svh'
    body.write_text('module Box(output y);\n`ifdef SYNTHESIS\n`include "value.svh"\n'
                    '`else\n`include "simulation.svh"\n`endif\nendmodule\n')
    header.write_text("assign y=1'b0;\n")
    simulation.write_text("assign y=1'b0;\n")
    work = tmp_path / 'work'
    work.mkdir()
    request = {'top': 'Box', 'files': [['root', str(body)]], 'inline': [], 'params': []}
    original = hdl.capture_batch([request], work)['results'][0]
    other = tmp_path / 'other'
    other.mkdir()
    path = {'root': body, 'include': header, 'simulation': simulation}[target]
    old = path.read_bytes()
    replacement = old.replace(b"1'b0", b"1'b1") if target != 'root' else b'module Broken; endmodule\n'
    # The tool version query is internal to Capture.tool. This boundary is the first HDL read.
    hook = race_injector.file(hdl, 'run_group', path, replacement, replace=replace, revert=revert)
    changed = hdl.capture_batch([request], other)['results'][0]
    assert hook.fired
    assert changed['chunks'] == original['chunks']
    files = changed['capture']['files']
    assert any(f['sha256'] == hashlib.sha256(old).hexdigest() for f in files)


def test_hdl_tool_edit_and_revert_refuses(tmp_path, race_injector):
    tool = tmp_path / 'yosys'
    tool.write_text('#!/bin/sh\nexec "' + shutil.which('yosys') + '" "$@"\n')
    tool.chmod(0o700)
    root = tmp_path / 'work'
    root.mkdir()
    request = {'top': 'Box', 'files': [], 'inline': [['verilog', 'module Box(output y); assign y=0; endmodule']],
               'params': [], 'yosys': str(tool)}
    hook = race_injector.file(hdl, 'run_group', tool, b'changed', when='after', revert=True)
    result = hdl.capture_batch([request], root)['results'][0]
    assert result['chunks'] == [] and 'input_not_captured' in result['problems'][0]
    assert hook.fired


def add_rtl(database, path):
    path.write_text('module GCD(input io_a, output io_result);\nwire x;\nendmodule\n')
    with sqlite3.connect(database) as con:
        con.execute('DELETE FROM rtl_files')
        con.execute('INSERT INTO rtl_files VALUES (?)', (str(path),))
        con.execute('UPDATE meta SET value=? WHERE key="schema"', ('rvw.designdb/20',))
        con.execute('CREATE TABLE IF NOT EXISTS input_files(path TEXT PRIMARY KEY, resolved TEXT, sha256 TEXT, size INTEGER, record TEXT)')
        con.execute('INSERT OR REPLACE INTO input_files VALUES (?,?,?,?,?)',
                    (str(path), str(path), hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, '{}'))


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_query_database_uses_captured_copy(gcd_db, tmp_path, race_injector, replace, revert):
    path = tmp_path / 'design.db'
    shutil.copyfile(gcd_db, path)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE meta SET value='Captured' WHERE key='toplevel'")
    other = tmp_path / 'other.db'
    shutil.copyfile(path, other)
    with sqlite3.connect(other) as con:
        con.execute("UPDATE meta SET value='Different' WHERE key='toplevel'")
    hook = race_injector.file(sqlite3, 'connect', path, other.read_bytes(), replace=replace, revert=revert)
    with closing(DesignDB(path)) as db:
        assert db.top == 'Captured'
        assert db.input.sha256 != hashlib.sha256(other.read_bytes()).hexdigest()
    assert hook.fired


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_where_uses_captured_rtl(gcd_db, tmp_path, race_injector, replace, revert):
    path = tmp_path / 'design.db'
    shutil.copyfile(gcd_db, path)
    rtl = tmp_path / 'GCD.v'
    add_rtl(path, rtl)
    # Capture.file has completed before parsing. The parser must read the private bytes.
    from rvw.common.capture import Capture
    hook = race_injector.file(Capture, 'file', rtl, b'module Different; endmodule\n', when='after',
                              replace=replace, revert=revert, occurrence=3)
    with closing(DesignDB(path)) as db:
        result = ops.where(db, 'x')
    assert hook.fired
    assert result['signal']['verilog']['loc'] == f'{rtl}:2'
    assert result['signal']['verilog']['sha256'] == hashlib.sha256(
        b'module GCD(input io_a, output io_result);\nwire x;\nendmodule\n').hexdigest()


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_where_refuses_changed_rtl(gcd_db, tmp_path, race_injector, replace, revert):
    path = tmp_path / 'design.db'
    shutil.copyfile(gcd_db, path)
    rtl = tmp_path / 'GCD.v'
    add_rtl(path, rtl)
    from rvw.common.capture import Capture
    hook = race_injector.file(Capture, 'file', rtl, b'module GCD;\n\nwire x;\nendmodule\n',
                              replace=replace, revert=revert, occurrence=3)
    with closing(DesignDB(path)) as db:
        result = ops.where(db, 'x')
    assert hook.fired
    assert result['status'] == 'inconclusive'
    assert 'input_not_captured:rtl' in result['cause']
    assert 'loc' not in result['signal']['verilog']
    from rvw.query.cli import render
    assert 'inconclusive: input_not_captured:rtl' in render('where', result)


@pytest.fixture(scope='session')
def capture_classpath():
    from rvw.common.proc import run_group
    repo = Path(__file__).resolve().parents[2]
    # Serialize sbt builds in this checkout, without blocking other worktrees.
    result = run_group([str(repo / 'scripts/with-lock.sh'), f'sbt-{repo.name}', 'nice', '-n', '10',
                        'sbt', '-batch', '-Dsbt.offline=true', 'export Test / fullClasspath'],
                       cwd=repo / 'SpinalDB/spinaldb', capture=True, timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr
    paths = [line for line in result.stdout.splitlines() if line.startswith('/') and '.jar' in line]
    assert paths, result.stdout
    return paths[-1]


class EmissionBoundary:
    def __init__(self, proc):
        self.proc = proc

    def emitted(self):
        lines = []
        for line in self.proc.stdout:
            lines.append(line)
            if line.strip() == 'CAPTURE_EMITTED':
                return ''.join(lines)
        raise AssertionError('JVM exited before emission: ' + ''.join(lines))

    def extract(self):
        self.proc.stdin.write('x\n')
        self.proc.stdin.flush()
        output = self.proc.communicate(timeout=60)[0]
        assert self.proc.returncode == 0, output


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_inline_fingerprint_is_the_emitted_text(tmp_path, capture_classpath, race_injector, replace, revert):
    # No threads or sleeps. Change the template at the named extraction boundary.
    template = tmp_path / 'template.v'
    original = b"module CaptureBox(output y); assign y=1'b1; endmodule\n"
    template.write_bytes(original)
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    proc = subprocess.Popen([java, '-Xss64m', '-cp', capture_classpath, 'spinaldb.CaptureFixtures', str(tmp_path)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    boundary = EmissionBoundary(proc)
    try:
        boundary.emitted()
        hook = race_injector.file(boundary, 'extract', template, original.replace(b"1'b1", b"1'b0"),
                                  replace=replace, revert=revert)
        boundary.extract()
        assert hook.fired
        assert (tmp_path / "inline-reads").read_text() == "1"
        assert "1'b1" in (tmp_path / 'rtl/CaptureTop.v').read_text()
        with closing(DesignDB(tmp_path / 'design.db')) as db:
            body_hash, key = db.q('SELECT body_sha256, key FROM blackboxes')[0]
        # Independently scan the emitted body, never the live template.
        result = hdl.execute({'requests': [{'top': 'CaptureBox', 'files': [], 'inline': [['verilog', original.decode()]], 'params': []}]})['results'][0]
        chunks = [base64.b64decode(data) for _, data in result['chunks']]
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(f'{len(chunk)}:'.encode())
            digest.update(chunk)
        assert not result['problems']
        assert body_hash == digest.hexdigest(), key
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_batch_shares_attribute_and_hdl_capture(tmp_path, race_injector, replace, revert):
    header = tmp_path / 'value.svh'
    header.write_bytes(b"assign y=1'b0;\n")
    body = tmp_path / 'Box.v'
    body.write_text('module Box(output y);\n`include "value.svh"\nendmodule\n')
    requests = [{'top': 'Box', 'files': [['body', str(body)]], 'inline': [], 'params': []}] * 2
    hook = race_injector.file(hdl, 'run_group', header, b"assign y=1'b1;\n", replace=replace, revert=revert)
    root = tmp_path / 'batch'
    root.mkdir()
    result = hdl.capture_batch(requests, root, [str(header)])
    assert hook.fired
    assert result['files']['problems'] == []
    assert base64.b64decode(result['files']['chunks'][0][1]) == b"assign y=1'b0;\n"
    for body_result in result['results']:
        assert body_result['problems'] == []
        assert any(base64.b64decode(b) == b"assign y=1'b0;\n" for _, b in body_result['chunks'])


def test_query_refuses_wal_database(gcd_db, tmp_path):
    path = tmp_path / 'wal.db'
    shutil.copyfile(gcd_db, path)
    with sqlite3.connect(path) as con:
        assert con.execute('PRAGMA journal_mode=WAL').fetchone() == ('wal',)
        con.execute("UPDATE meta SET value='WAL' WHERE key='toplevel'")
        con.commit()
        from rvw.query.db import QueryError
        with pytest.raises(QueryError, match='input_not_captured:database.*WAL'):
            DesignDB(path)


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_diff_same_lookup_is_captured_once(gcd_db, tmp_path, race_injector, replace, revert):
    from rvw.query.cli import _diff
    from argparse import Namespace
    path = tmp_path / 'design.db'
    shutil.copyfile(gcd_db, path)
    changed = tmp_path / 'changed.db'
    shutil.copyfile(gcd_db, changed)
    with sqlite3.connect(changed) as con:
        con.execute("UPDATE signals SET width=width+1 WHERE path='x'")
    hook = race_injector.file(DesignDB, '__init__', path, changed.read_bytes(), replace=replace,
                              revert=revert, occurrence=2)
    result = _diff(None, Namespace(old=path, new=path, scope=None, limit=200, no_connections=False))
    assert hook.fired
    assert result['summary']['identical'] is True
    assert result['input_capture']['old'] == result['input_capture']['new']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_where_source_uses_content_binding(gcd_db, tmp_path, race_injector, replace, revert):
    path = tmp_path / 'design.db'
    shutil.copyfile(gcd_db, path)
    source = tmp_path / 'Source.scala'
    source.write_bytes(b'// captured source\n')
    rtl = tmp_path / 'GCD.v'
    add_rtl(path, rtl)
    with sqlite3.connect(path) as con:
        con.execute('UPDATE files SET path=? WHERE id=(SELECT file_id FROM signals WHERE path="x")', (str(source),))
        con.execute('INSERT INTO input_files VALUES (?,?,?,?,?)',
                    (str(source), str(source), hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size, '{}'))
    from rvw.common.capture import Capture
    hook = race_injector.file(Capture, 'file', source, b'// changed source\n', replace=replace,
                              revert=revert, occurrence=2, when='after')
    with closing(DesignDB(path)) as db:
        result = ops.where(db, 'x')
    assert hook.fired
    assert result['signal']['source']['sha256'] == hashlib.sha256(b'// captured source\n').hexdigest()
    assert result['signal']['source']['source'] == str(source)


def test_export_failure_preserves_published_file(gcd_db, tmp_path, race_injector):
    path = tmp_path / 'artifact.json'
    path.write_bytes(b'previous artifact')

    def fail():
        raise OSError('publication stopped')

    hook = race_injector.at(ops.os, 'replace', fail, when='before')
    with closing(DesignDB(gcd_db)) as db:
        with pytest.raises(OSError, match='publication stopped'):
            ops.export(db, 'pdg', str(path))
    assert hook.fired
    assert path.read_bytes() == b'previous artifact'
    assert not list(tmp_path.glob('.rvw-export-*'))


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
@pytest.mark.parametrize('target', ['root', 'include'])
def test_scala_hdl_scan_binds_yosys_reads(tmp_path, capture_classpath, replace, revert, target):
    """Use the shared injector in the child runner at the actual Yosys-read boundary.

    The old scanner hashed restored live bytes, even though Yosys read changed bytes.
    Preserve the tool's ppdump as independent evidence before its private directory closes.
    """
    import json
    from rvw.common.proc import run_group
    repo = Path(__file__).resolve().parents[2]
    body, header = tmp_path / 'Box.v', tmp_path / 'value.svh'
    body.write_text('module Box(output y);\n`include "value.svh"\nendmodule\n' if target == 'include' else
                    'module Box(output y); assign y = 0; endmodule\n')
    header.write_text('assign y = 0;\n')
    live = body if target == 'root' else header
    before = live.read_bytes()
    runner = tmp_path / 'race_runner.py'
    # Inject at the C8 runner boundary without source sleeps or production hooks.
    runner.write_text(f'''import json, sys
from pathlib import Path
import pytest
sys.path[:0] = {repr([str(repo / 'SpinalDB/scripts'), str(repo / 'rvw/src'), str(repo / 'rvw/tests')])}
from race_injection import RaceInjector
root = Path({str(tmp_path)!r})
live = Path({str(live)!r})
replacement = {before.replace(b'= 0', b'= 1')!r}
import hdl_capture as owner
hook = RaceInjector(pytest.MonkeyPatch()).file(owner, 'run_group', live, replacement,
                                              replace={replace!r}, revert={revert!r})
raced = owner.run_group

def observed(argv, *args, **kw):
    result = raced(argv, *args, **kw)
    if '-s' in argv:
        script = Path(argv[argv.index('-s') + 1])
        dumps = [p.read_text() for p in script.parent.glob('pp*.txt')]
        with (root / 'pp-evidence.jsonl').open('a') as stream:
            stream.write(json.dumps(dumps) + '\\n')
    return result

owner.run_group = observed
try:
    request = json.loads(Path(sys.argv[2]).read_text())
    Path(sys.argv[3]).write_text(json.dumps(owner.execute(request)))
finally:
    (root / 'race-fired').write_text(str(hook.fired))
''')
    env = {**os.environ, 'SPINALDB_PYTHON': sys.executable, 'SPINALDB_PROCESS_RUNNER': str(runner)}
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath, 'spinaldb.CaptureDepsFixtures', str(tmp_path)],
                       env=env, capture=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'race-fired').read_text() == 'True'
    scan = json.loads((tmp_path / 'scan.json').read_text())
    assert scan['problems'] == [], scan['problems']
    assert any(base64.b64decode(data) == before for _, data in scan['chunks'])
    evidence = (tmp_path / 'pp-evidence.jsonl').read_text()
    assert 'assign y = 0' in evidence
    assert 'assign y = 1' not in evidence


@pytest.mark.parametrize('record', [None, {}, {'schema': 'rvw.capture/1', 'problems': ['input_not_captured:rtl']}])
def test_diff_refuses_missing_or_failed_capture(gcd_db, tmp_path, record):
    import json
    from rvw.query.diff import diff
    path = tmp_path / 'design.db'
    shutil.copyfile(gcd_db, path)
    with sqlite3.connect(path) as con:
        if record is None:
            con.execute("DELETE FROM meta WHERE key='input_capture'")
        else:
            con.execute("UPDATE meta SET value=? WHERE key='input_capture'", (json.dumps(record),))
    with closing(DesignDB(path)) as db:
        result = diff(db, db)
    assert result['status'] == 'inconclusive'
    assert result['summary']['identical'] is None
    assert '<input_capture>' in result['undetermined']['paths']


def test_partial_batch_capture_cannot_complete_body(tmp_path, race_injector):
    from rvw.common.capture import Capture
    source = tmp_path / 'navigation.v'
    source.write_bytes(b'captured source')
    original = source.read_bytes()
    hook = race_injector.at(Capture, 'file', source.unlink, when='before',
                            restore=lambda: source.write_bytes(original))
    root = tmp_path / 'batch'
    root.mkdir()
    result = hdl.capture_batch([{'top': 'Box', 'files': [], 'inline': [['verilog',
                                'module Box(output y); assign y = 0; endmodule']], 'params': []}], root, [str(source)])
    assert hook.fired
    assert result['results'][0]['chunks'] == []
    assert 'input_not_captured:batch' in result['results'][0]['problems'][0]


def test_hdl_records_an_ordinary_yosys_launcher(tmp_path):
    import shlex

    tool = tmp_path / 'yosys'
    tool.write_text('#!/bin/sh\n# Site-specific launcher.\nexec ' + shlex.quote(shutil.which('yosys')) + ' "$@"\n')
    tool.chmod(0o700)
    root = tmp_path / 'work'
    root.mkdir()
    request = {'top': 'Box', 'files': [], 'inline': [['verilog', 'module Box(output y); assign y=0; endmodule']],
               'params': [], 'yosys': str(tool)}
    batch = hdl.capture_batch([request], root)
    (result,) = batch['results']
    assert result['problems'] == [] and result['chunks']
    (record,) = result['capture']['tools']
    assert record['path'] == str(tool)
    assert record['sha256'] == hashlib.sha256(tool.read_bytes()).hexdigest()
