"""Probe MCP tools."""
from rvw.mcp.spec import ToolSpec, schema

from .convert import CONVERTERS

S = {'type': 'string'}


def _list(db=None, events=None):
    from . import api
    return api.report(db=db, events=events)


def _summary(events):
    from . import api
    return api.summary(events)


def _convert(events, to, out, c2=None, c1=None, probe=None, roi_start=None, roi_end=None):
    from . import api
    roi = (roi_start, roi_end) if roi_start is not None and roi_end is not None else None
    return api.run_convert(events, to, out, c2=c2, c1=c1, probe=probe, roi=roi)


def mcp_tools():
    return [
        ToolSpec('probes_list', 'List simulation probes from a design database (db) or a probe event stream '
                 '(events), and for each consumer tool whether the probes enable it or which events are missing.',
                 schema({'db': S, 'events': S}, []), _list, annotations={'readOnlyHint': True}),
        ToolSpec('probes_summary', 'Event counts and counter totals of a rvw.probe-events/1 stream.',
                 schema({'events': S}, ['events']), _summary, annotations={'readOnlyHint': True}),
        ToolSpec('probes_convert', 'Convert a rvw.probe-events/1 stream into a consumer format: '
                 + ', '.join(sorted(CONVERTERS)) + '. bp-events, counts and interrupts need the run C2 (c2); '
                 'counts also needs C1 (c1). Refuses events that do not align with C2.',
                 schema({'events': S, 'to': {'type': 'string', 'enum': sorted(CONVERTERS)}, 'out': S, 'c2': S,
                         'c1': S, 'probe': S, 'roi_start': {'type': 'integer'}, 'roi_end': {'type': 'integer'}},
                        ['events', 'to', 'out']), _convert),
    ]
