"""Small synchronous LSP server. The design database is the semantic authority."""
from __future__ import annotations
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

from rvw.query import ops, semantic
from rvw.query.db import DesignDB, QueryError


def location(file, line):
    if not file or not line:
        return None
    return {'uri': Path(file).absolute().as_uri(), 'range': {
        'start': {'line': max(0, line-1), 'character': 0},
        'end': {'line': max(0, line-1), 'character': 0}}}


class Server:
    def __init__(self, db, lint_settings=None):
        self.path = db
        self.documents = {}
        self.lint_settings = lint_settings
        self.shutdown = False

    def text(self, uri):
        if uri in self.documents:
            return self.documents[uri]
        return Path(unquote(urlparse(uri).path)).read_text()

    def resolve(self, db, params):
        uri, pos = params['textDocument']['uri'], params['position']
        lines = self.text(uri).splitlines()
        if pos['line'] >= len(lines):
            raise QueryError('position is outside the document')
        line = lines[pos['line']]
        # LSP positions use UTF-16 code units.
        column = len(line.encode('utf-16-le')[:pos['character']*2].decode('utf-16-le', errors='ignore'))
        tokens = list(re.finditer(r'[A-Za-z_$][A-Za-z_0-9$]*(?:\.[A-Za-z_$][A-Za-z_0-9$]*)*', line))
        token = next((m[0] for m in tokens if m.start() <= column < m.end()), None)
        if token is None:
            raise QueryError('no signal at this position')
        file = str(Path(unquote(urlparse(uri).path)).resolve())
        # A declaration line is authoritative even when an instance name is absent in source.
        candidates = db.signals_where('f.path=? AND s.line=? AND s.pruned=0', (file, pos['line']+1))
        candidates = [s for s in candidates if s.name == token or s.spinal_path == token or s.spinal_path.endswith('.'+token)]
        if len(candidates) == 1:
            return candidates[0]
        # Restrict RTL names to the enclosing module when the module is known.
        before = '\n'.join(lines[:pos['line']+1])
        modules = list(re.finditer(r'\bmodule\s+([A-Za-z_$][\w$]*)', before))
        if modules:
            ids = [i for (i,) in db.q('SELECT id FROM components WHERE module=?', (modules[-1][1],))]
            candidates = [s for cid in ids for s in db.signals_where('s.component_id=? AND s.name=? AND s.pruned=0', (cid, token))]
            if len(candidates) == 1:
                return candidates[0]
            # Repeated module instances can share a declaration. Do not select one silently.
        return db.resolve_one(token)

    def request(self, method, params):
        if method == 'initialize':
            return {'capabilities': {'positionEncoding': 'utf-16', 'textDocumentSync': 1,
                    'definitionProvider': True, 'referencesProvider': True,
                    'hoverProvider': True, 'documentSymbolProvider': True},
                    'serverInfo': {'name': 'rvw lsp', 'version': '1'}}
        if method == 'shutdown':
            self.shutdown = True
            return None
        if method in ('initialized', '$/cancelRequest', 'textDocument/didClose'):
            if method == 'textDocument/didClose':
                self.documents.pop(params['textDocument']['uri'], None)
            return None
        if method == 'textDocument/didOpen':
            self.documents[params['textDocument']['uri']] = params['textDocument']['text']
            return None
        if method == 'textDocument/didChange':
            self.documents[params['textDocument']['uri']] = params['contentChanges'][-1]['text']
            return None
        if method == 'textDocument/didSave':
            return None
        db = DesignDB(self.path)
        try:
            if method == 'textDocument/documentSymbol':
                file = str(Path(unquote(urlparse(params['textDocument']['uri']).path)).resolve())
                return [{'name': s.path, 'kind': 13, 'range': loc['range'], 'selectionRange': loc['range'],
                         'detail': f'{s.type}[{s.width}] {s.kind}'}
                        for s in db.signals_where('f.path=? AND s.pruned=0 AND s.generated=0', (file,))
                        if (loc := location(s.file, s.line))]
            s = self.resolve(db, params)
            if method == 'textDocument/definition':
                loc = location(s.file, s.line)
                return [loc] if loc else []
            if method == 'textDocument/hover':
                d = ops.drivers(db, s.path)
                return {'contents': {'kind': 'plaintext', 'value': json.dumps({
                    'signal': d['signal'], 'register': d.get('register'),
                    'drivers': d['assignments'], 'graph_semantics': db.meta.get('graph_semantics'),
                    'database_warnings': db.staleness(),
                    'note': 'Captured elaboration. Rebuild after source changes.'}, indent=2)}}
            if method == 'textDocument/references':
                refs = semantic.references(db, s.path)
                locs = []
                if params.get('context', {}).get('includeDeclaration'):
                    locs.append(location(s.file, s.line))
                for row in refs['statements'] + refs['assignments'] + refs['conditions']:
                    text = row.get('loc')
                    if text and ':' in text:
                        file, line = text.rsplit(':', 1)
                        locs.append(location(file, int(line)))
                return list({json.dumps(l, sort_keys=True): l for l in locs if l}.values())
            raise NotImplementedError(method)
        finally:
            db.close()

    def diagnostics(self, uri):
        if not self.lint_settings:
            return []
        from rvw.lint.cli import report_outputs
        report = report_outputs(self.lint_settings)
        result = []
        file = str(Path(unquote(urlparse(uri).path)).resolve())
        findings = [f for run in report.get('backends', {}).values() for f in run.get('findings', [])]
        for finding in findings:
            if finding.get('disposition') == 'waived' or str(Path(finding.get('file') or '').resolve()) != file:
                continue
            loc = location(file, finding.get('line') or 1)
            result.append({'range': loc['range'], 'severity': 1 if finding.get('severity') == 'error' else 2,
                           'message': finding.get('message', str(finding)), 'source': 'rvw lint',
                           'code': finding.get('rule')})
        return result


def read_message(stream):
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b'\r\n', b'\n'):
            break
        key, value = line.decode('ascii').split(':', 1)
        headers[key.lower()] = value.strip()
    size = int(headers['content-length'])
    payload = stream.read(size)
    if len(payload) != size:
        raise ValueError('truncated LSP message')
    return json.loads(payload)


def write_message(stream, message):
    raw = json.dumps(message).encode()
    stream.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode() + raw)
    stream.flush()


def serve(server, source, sink):
    while (message := read_message(source)) is not None:
        method, params = message.get('method'), message.get('params') or {}
        if method == 'exit':
            return 0 if server.shutdown else 1
        response = None
        try:
            result = server.request(method, params)
            response = {'jsonrpc': '2.0', 'id': message.get('id'), 'result': result}
            if method in ('textDocument/didOpen', 'textDocument/didSave') and server.lint_settings:
                uri = params['textDocument']['uri']
                write_message(sink, {'jsonrpc': '2.0', 'method': 'textDocument/publishDiagnostics',
                                     'params': {'uri': uri, 'diagnostics': server.diagnostics(uri)}})
        except (QueryError, OSError, ValueError, KeyError, NotImplementedError) as exc:
            code = -32601 if isinstance(exc, NotImplementedError) else -32602
            response = {'jsonrpc': '2.0', 'id': message.get('id'), 'error': {'code': code, 'message': str(exc)}}
            if 'id' not in message:
                write_message(sink, {'jsonrpc': '2.0', 'method': 'window/logMessage',
                                     'params': {'type': 2, 'message': str(exc)}})
        if 'id' in message:
            write_message(sink, response)
    return 0
