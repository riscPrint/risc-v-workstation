from rvw.mcp.spec import ToolSpec, schema
from .index import build, query


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('evidence_index', 'Index C1/C3/C4/C5, formal, coverage and lint report references without rewriting originals.',
        schema({'root': string, 'db': string}, ['root', 'db']), build, long=True),
        ToolSpec('evidence_query', 'Find original observations, configuration, assumptions and invalidating dependencies. No verdict is inferred.',
        schema({'db': string, 'text': string, 'schema': string}, ['db']), query, annotations={'readOnlyHint': True})]
