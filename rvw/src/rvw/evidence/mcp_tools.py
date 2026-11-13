from rvw.mcp.spec import ToolSpec, schema
from .index import build, query
from rvw.mcp.worker import handler


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('evidence_index', 'Index C1/C3/C4/C5, formal, coverage and lint report references without rewriting originals.',
        schema({'root': string, 'db': string}, ['root', 'db']), handler('rvw.evidence.index', function='build'), long=True, side_effects='long-running; writes the index database at db', native_tools=()),
        ToolSpec('evidence_query', 'Find original observations, configuration, assumptions and invalidating dependencies. No verdict is inferred.',
        schema({'db': string, 'text': string, 'schema': string}, ['db']), query, annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]
