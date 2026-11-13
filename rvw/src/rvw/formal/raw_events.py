"""Replay explicit top-input property events before each timestamp's input update.

Private monitor pulses sample the settled state from the preceding timestamp.
They are simulation controls, never a replacement formal clock model.
"""
import re

from .sva import _group
from .temporal import Unsupported

PREFIX = 'rvw_raw_event_'


def parse(text):
    terms = re.split(r'\s+or\s+|\s*,\s*', text.strip())
    events = []
    for term in terms:
        match = re.fullmatch(r'(?:(posedge|negedge)\s+)?([A-Za-z_]\w*)', term.strip())
        if not match:
            raise Unsupported('raw_event_expression', text)
        events.append(dict(edge=match[1] or 'change', signal=match[2]))
    return events


def rewrite(source, top, force=False):
    text = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m:' '*len(m[0]), source, flags=re.S)
    if PREFIX in text:
        raise Unsupported('reserved_identifier', PREFIX)
    candidates = []
    for module in re.finditer(r'\bmodule\s+(\w+)\b.*?\bendmodule\b', text, re.S):
        spans = []
        for prop in re.finditer(r'\b(assert|assume|cover)\s+property\s*\(', module[0]):
            body, end = _group(text, module.start()+prop.end()-1)
            spans.append((module.start()+prop.end(), body, False))
        for prop in re.finditer(r'\bproperty\s+\w+\s*;(.*?)\bendproperty\b', module[0], re.S):
            spans.append((module.start()+prop.start(1), prop[1], True))
        for start, body, named in spans:
            clock = re.search(r'@\s*\(', body) if named else re.match(r'\s*@\s*\(', body)
            if not clock:
                continue
            event, event_end = _group(body, clock.end()-1)
            terms = parse(event)
            ordinary = len(terms)==1 and terms[0]['edge']=='posedge'
            candidates.append((module, start, body, clock, event_end, event, terms, ordinary))
    if not force and all(row[-1] for row in candidates):
        return source, []
    if re.search(r'\b(checker|bind)\b', text):
        raise Unsupported('raw_event_scope', 'checker and bind replay needs instance clocks')
    edits, bindings = [], []
    # Once a job has raw events, sample its other property clocks in the same
    # pre-update phase. This also preserves old values of other changing clocks.
    for module, start, body, clock, event_end, event, terms, ordinary in candidates:
        if re.search(r'\bdisable\s+iff\b', body[event_end:]):
            raise Unsupported('raw_event_disable', 'same-timestamp cancellation is not qualified')
        if module[1] != top:
            raise Unsupported('raw_event_scope', 'event replay properties must be in the top module')
        name = PREFIX+str(len(bindings))
        edits.append((start+clock.start(), start+event_end, f'@(posedge {name})'))
        # Insert the private clock before all declarations and statements that
        # use it. The module header can contain parameter semicolons only inside
        # parentheses; locate its first top-level semicolon.
        depth = 0
        point = None
        for index, char in enumerate(module[0]):
            depth += (char=='(')-(char==')')
            if char==';' and depth==0:
                point=module.start()+index+1
                break
        if point is None:
            raise Unsupported('raw_event_module_header')
        edits.append((point,point,f'\nreg {name}=0;\n'))
        bindings.append(dict(clock=name, event=event.strip(), terms=terms))
    for start,end,replacement in sorted(edits, reverse=True):
        source=source[:start]+replacement+source[end:]
    return source,bindings


def validate(bindings, inputs):
    for binding in bindings:
        for term in binding['terms']:
            if term['signal'] not in inputs:
                raise Unsupported('raw_event_port', term['signal'])
            if term['edge'] != 'change' and inputs[term['signal']] != 1:
                raise Unsupported('raw_event_width', term['signal'])


def edge(before, after, kind):
    before, after = before.lower(), after.lower()
    if kind=='change':
        return before!=after
    if kind=='posedge':
        return before=='0' and after in ('1','x','z') or before in ('x','z') and after=='1'
    return before=='1' and after in ('0','x','z') or before in ('x','z') and after=='0'


def pulses(rows, bindings, inputs):
    previous={name:'x'*width for name,width in inputs.items()}
    result=[]
    for index,(at,changes) in enumerate(rows):
        current=previous|changes
        if index == 0:
            result.append([])
            previous=current
            continue
        result.append([binding['clock'] for binding in bindings
                       if any(edge(previous[term['signal']], current[term['signal']],term['edge'])
                              for term in binding['terms'])])
        previous=current
    return result
