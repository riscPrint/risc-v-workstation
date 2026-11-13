"""Agent access to language server operations without an editor."""
from rvw.mcp.spec import ToolSpec, schema


def request(db, method, params=None):
    from .server import Server
    return {'result': Server(db).request(method, params or {})}


def mcp_tools():
    return [ToolSpec('lsp_request', 'Query captured LSP navigation without an editor', schema({
        'db': {'type': 'string'}, 'method': {'type': 'string', 'enum': [
            'textDocument/definition', 'textDocument/references', 'textDocument/hover', 'textDocument/documentSymbol']},
        'params': {'type': 'object'}}, ['db', 'method', 'params']), request,
        annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]
