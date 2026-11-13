import io
import json
import pytest
from rvw.lsp.server import Server, serve, read_message, write_message
from rvw.query.db import DesignDB, QueryError

pytestmark = pytest.mark.fast


def test_stdio_lifecycle(cluster_db):
    source, sink = io.BytesIO(), io.BytesIO()
    for message in [
        {'id': 1, 'method': 'initialize', 'params': {}},
        {'method': 'initialized'},
        {'id': 2, 'method': 'shutdown'},
        {'method': 'exit'},
    ]:
        write_message(source, {'jsonrpc': '2.0', **message})
    source.seek(0)
    assert serve(Server(cluster_db), source, sink) == 0
    sink.seek(0)
    assert read_message(sink)['result']['capabilities']['hoverProvider']
    assert read_message(sink)['id'] == 2
    assert read_message(sink) is None


def test_navigation(cluster_db):
    server = Server(cluster_db)
    uri = 'file:///tmp/rvw-lsp-test.sv'
    server.request('textDocument/didOpen', {'textDocument': {'uri': uri, 'text': 'fifo.logic_ptr_push'}})
    params = {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 8}}
    d = server.request('textDocument/definition', params)
    assert d and d[0]['uri'].endswith('.scala')
    h = json.loads(server.request('textDocument/hover', params)['contents']['value'])
    assert h['signal']['width'] == 3 and h['drivers']
    params['context'] = {'includeDeclaration': True}
    assert server.request('textDocument/references', params)
    db = DesignDB(cluster_db)
    try:
        s = db.resolve_one('fifo.logic_ptr_push')
        symbols = server.request('textDocument/documentSymbol', {'textDocument': {'uri': __import__('pathlib').Path(s.file).as_uri()}})
        assert any(row['name'] == s.path for row in symbols)
    finally:
        db.close()
    server.request('textDocument/didChange', {'textDocument': {'uri': uri}, 'contentChanges': [{'text': 'x'}]})
    with pytest.raises(QueryError, match='ambiguous'):
        server.request('textDocument/definition', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 0}})


def test_lint_diagnostics(monkeypatch, cluster_db):
    monkeypatch.setattr('rvw.lint.cli.report_outputs', lambda path: {'backends': {'rules': {'findings': [
        {'file': '/tmp/a.sv', 'line': 4, 'rule': 'lint.test', 'message': 'undriven', 'severity': 'error', 'disposition': 'active'},
        {'file': '/tmp/a.sv', 'line': 8, 'rule': 'lint.other', 'disposition': 'waived'}]}}})
    ds = Server(cluster_db, 'settings.json').diagnostics('file:///tmp/a.sv')
    assert len(ds) == 1 and ds[0]['range']['start']['line'] == 3 and ds[0]['severity'] == 1
