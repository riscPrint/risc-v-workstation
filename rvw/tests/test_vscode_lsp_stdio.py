"""Exercise the client protocol against a captured extractor database over stdio."""
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest
from rvw.lsp.server import read_message, write_message
from rvw.query.db import DesignDB

pytestmark = pytest.mark.fast


def test_client_session_over_stdio(cluster_db, tmp_path):
    db = DesignDB(cluster_db)
    try:
        signal = db.resolve_one('fifo.logic_ptr_push')
    finally:
        db.close()
    from rvw.lint.cli import report
    settings = tmp_path / 'lint.json'
    settings.write_text(json.dumps({'schema': 'rvw.lint-settings/1',
        'config': 'test', 'top': 'GcdCluster', 'db': str(cluster_db),
        'backends': ['rules', 'structural']}))
    lint = report(settings)
    expected = [f for run in lint['backends'].values() for f in run['findings']
                if f.get('file') == signal.file and f.get('disposition') != 'waived']
    uri = Path(signal.file).as_uri()
    document = {'uri': uri}
    position = {'textDocument': document, 'position': {'line': 0, 'character': 8}}
    messages = [
        {'id': 1, 'method': 'initialize', 'params': {}},
        {'method': 'initialized'},
        {'method': 'textDocument/didOpen', 'params': {'textDocument': {
            **document, 'languageId': 'scala', 'version': 1, 'text': 'fifo.logic_ptr_push'}}},
        {'id': 2, 'method': 'textDocument/definition', 'params': position},
        {'id': 3, 'method': 'textDocument/hover', 'params': position},
        {'id': 4, 'method': 'textDocument/references', 'params': {
            **position, 'context': {'includeDeclaration': True}}},
        {'id': 5, 'method': 'textDocument/documentSymbol', 'params': {'textDocument': document}},
        {'id': 6, 'method': 'shutdown'},
        {'method': 'exit'},
    ]
    source = io.BytesIO()
    for message in messages:
        write_message(source, {'jsonrpc': '2.0', **message})
    run = subprocess.run([sys.executable, '-m', 'rvw', 'lsp', '--db', str(cluster_db), '--lint-settings', str(settings)],
                         input=source.getvalue(), capture_output=True, timeout=20)
    assert run.returncode == 0, run.stderr.decode()
    sink = io.BytesIO(run.stdout)
    replies = []
    while (reply := read_message(sink)) is not None:
        replies.append(reply)
    assert all('error' not in reply for reply in replies), replies
    results = {reply['id']: reply['result'] for reply in replies if 'id' in reply}
    assert results[1]['capabilities']['definitionProvider']
    assert results[2][0]['uri'] == uri
    hover = json.loads(results[3]['contents']['value'])
    assert hover['signal']['width'] == 3
    assert results[4]
    assert any(row['name'] == signal.path for row in results[5])
    assert results[6] is None

    diagnostics = [r['params']['diagnostics'] for r in replies
                   if r.get('method') == 'textDocument/publishDiagnostics']
    assert len(diagnostics) == 1
    assert len(diagnostics[0]) == len(expected)
    assert [d['code'] for d in diagnostics[0]] == [f['rule'] for f in expected]
