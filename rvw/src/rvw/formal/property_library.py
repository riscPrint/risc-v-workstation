"""SVA snippets for common bounded interface intents.

These are explicit contracts, not inferred design specifications. Snippets live
inside the module that owns the signals. No bind or proprietary SVA tool is used.
"""
import json
from pathlib import Path
import re

from .temporal import Unsupported, lower

KINDS = ('handshake', 'fifo', 'one-hot', 'arbiter-fairness', 'request-response', 'flow')
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def ident(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise ValueError(f'expected a plain RTL identifier, got {value!r}')
    return value


def render(spec):
    kind = spec['kind']
    if kind not in KINDS:
        raise Unsupported('property_intent', kind)
    name = ident(spec['id'])
    clock = ident(spec.get('clock', 'clk'))
    reset = spec.get('reset')
    if reset is not None:
        reset = ident(reset)
    disable = f'disable iff ({reset}) ' if reset else ''
    header = f'@(posedge {clock}) {disable}'
    declarations = []
    properties = []
    def prop(suffix, body):
        properties.append(f'{name}_{suffix}: assert property ({header}{body});')
    def signal(key):
        return ident(spec[key])
    def previous(key, width):
        old = f'rvw_intent_{name}_{key}'
        declarations.append(f'reg [{width-1}:0] {old};\nalways @(posedge {clock}) {old} <= {signal(key)};')
        return old
    if kind == 'handshake':
        valid, ready = signal('valid'), signal('ready')
        prop('hold', f'{valid} && !{ready} |=> {valid}')
        width = spec.get('width', 1)
        _positive(width, 'width')
        old = previous('payload', width)
        prop('stable', f'{valid} && !{ready} |=> {signal("payload")} == {old}')
    elif kind == 'flow':
        # Flow has no backpressure. Holding payload or valid on the next cycle
        # would impose Stream semantics. Only check a declared value bound.
        bound = spec.get('max_value')
        if type(bound) is not int or bound < 0:
            raise ValueError('Flow needs an explicit nonnegative max_value contract')
        prop('payload_range', f'{signal("valid")} |-> {signal("payload")} <= {bound}')
    elif kind == 'one-hot':
        bits = signal('bits')
        prop('onehot0', f'({bits} & ({bits} - 1\'b1)) == 0')
        if not spec.get('allow_zero', True):
            prop('nonzero', f'{bits} != 0')
    elif kind in ('request-response', 'arbiter-fairness'):
        bound = spec.get('bound', 8)
        _positive(bound, 'bound')
        if bound > 64:
            raise Unsupported('range_limit', str(bound))
        request = signal('request')
        response = signal('grant' if kind == 'arbiter-fairness' else 'response')
        minimum = spec.get('minimum', 0)
        if type(minimum) is not int or not 0 <= minimum <= bound:
            raise ValueError('minimum must be between zero and bound')
        prop('response', f'{request} |-> 1 ##[{minimum}:{bound}] {response}')
    else:
        depth, width = spec['depth'], spec['width']
        _positive(depth, 'depth')
        _positive(width, 'width')
        if depth >= 2**width:
            raise ValueError('width must represent depth')
        count, push, pop = signal('count'), signal('push'), signal('pop')
        prop('range', f'{count} <= {depth}')
        prop('overflow', f'{push} && !{pop} |-> {count} < {depth}')
        prop('underflow', f'{pop} && !{push} |-> {count} > 0')
        old = previous('count', width)
        oldpush, oldpop = previous('push', 1), previous('pop', 1)
        prop('count_step', f'1 |=> {count} == {old} '
             f'+ ({oldpush} ? {width+1}\'d1 : {width+1}\'d0) '
             f'- ({oldpop} ? {width+1}\'d1 : {width+1}\'d0)')
    return '\n'.join(declarations + properties) + '\n'


def _positive(value, name):
    if type(value) is not int or not 1 <= value <= 4096:
        raise ValueError(f'{name} must be in 1..4096')


def from_channels(report, bindings):
    """Use actual SpinalChecks channel types. Never guess names from suffixes.

    Bindings supply clock/reset and payload widths absent from rvw.checks/1.
    A channel without a reviewed binding gives an unsupported diagnostic.
    """
    if report.get('schema') != 'rvw.checks/1':
        raise ValueError('expected rvw.checks/1')
    specs = []
    for channel in report.get('channels', []):
        key = channel['path'] + '.' + channel['object']
        if key not in bindings:
            raise Unsupported('channel_clock_binding', key)
        binding = bindings[key]
        if channel['kind'] not in ('Stream', 'Flow', 'stream', 'flow'):
            raise Unsupported('channel_type', channel['kind'])
        # Hierarchical nets need an explicit local RTL port mapping. A snippet
        # must not silently choose another instance's similarly named signal.
        ports = binding['ports']
        for role in ('valid', 'ready'):
            if channel.get(role) is not None and channel[role] not in ports:
                raise Unsupported('channel_port_binding', channel[role])
        payloads = channel.get('payload', [])
        if len(payloads) != 1 or payloads[0] not in ports:
            raise Unsupported('channel_payload_binding', key)
        spec = dict(binding)
        spec.update(kind='handshake' if channel['kind'].lower() == 'stream' else 'flow',
                    valid=ports[channel['valid']], payload=ports[payloads[0]])
        if channel.get('ready') is not None:
            spec['ready'] = ports[channel['ready']]
        specs.append(spec)
    return specs


def run(args):
    spec = json.loads(Path(args.spec).read_text())
    if args.channels:
        intents = from_channels(json.loads(Path(args.channels).read_text()), spec)
    else:
        intents = spec['properties']
    ids = [i['id'] for i in intents]
    if len(set(ids)) != len(ids) or not ids:
        raise ValueError('declare nonempty intents with unique ids')
    source = '\n'.join(render(intent) for intent in intents)
    # Parse every generated property before publication. This catches any
    # mismatch between this library and the finite temporal frontend.
    lower('module rvw_intents;\n' + source + '\nendmodule')
    Path(args.out).write_text(source)
    return 0
