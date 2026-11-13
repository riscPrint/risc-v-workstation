from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('evidence_index', 'Index C1/C3/C4/C5, formal, coverage and lint report references without rewriting originals.',
        schema({'root': string, 'db': string}, ['root', 'db']), handler('rvw.evidence.index', function='build'), long=True, side_effects='long-running; writes the index database at db', native_tools=()),
        ToolSpec('evidence_query', 'Find original observations, configuration, assumptions and invalidating dependencies. No verdict is inferred.',
        schema({'db': string, 'text': string, 'schema': string}, ['db']), query, annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]


def build(root, db):
    """Load the handler on first use."""
    from rvw.evidence.index import build as implementation
    return implementation(root, db)

def query(db, text='', schema=None):
    """Load the handler on first use."""
    from rvw.evidence.index import query as implementation
    return implementation(db, text, schema)
