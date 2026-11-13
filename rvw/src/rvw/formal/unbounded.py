"""Small single-clock SVA automata with explicit infinite-trace acceptance.

Supported operands are Boolean expressions. All requests retain their own
obligation. A breakpoint set prevents new requests from starving old ones.
"""
import re

from .sva import _group
from .sampled import emit as sampled_emit
from .temporal import Unsupported, split, unwrap

LIMIT = 64
MARKER = re.compile(r'\bs_eventually\b|\b(?:s_)?until(?:_with)?\b|##\s*\[[^\]]*\$|\[\s*(?:\*|->|=)')


class Monitor:
    def __init__(self, clock, prefix):
        self.clock, self.prefix = clock, prefix
        self.lines = []
        self.expression_count = 0
        self.guard = None

    def expression(self, text):
        try:
            value, history = sampled_emit(unwrap(text), self.clock,
                                          f'{self.prefix}_sample{self.expression_count}')
        except Unsupported:
            raise
        except ValueError as error:
            raise Unsupported('liveness_boolean', str(error)) from error
        self.expression_count += 1
        self.lines.extend(history)
        return value

    def state(self, name, expr, width=1):
        name = self.prefix + '_' + name
        packed = '' if width == 1 else f'[{width-1}:0] '
        self.lines += [f'reg {packed}{name} = 0;',
                       f'always @(posedge {self.clock}) {name} <= {expr};']
        return name

    def delay(self, expr, count, name):
        if not 0 <= count <= LIMIT:
            raise Unsupported('liveness_capacity', f'maximum delay {LIMIT}')
        taps = [expr]
        for index in range(count):
            taps.append(self.state(f'{name}_{index}', taps[-1]))
        return taps

    def pending(self, request, response):
        name = self.prefix + '_pending'
        return self.state('pending', f'({name} || ({request})) && !({response})')

    def fatal(self, expr):
        name = self.prefix + '_fatal'
        return self.state('fatal', f'{name} || ({expr})')

    def finish(self, progress, active='0'):
        if self.guard is not None:
            name = self.prefix + '_throughout_failed'
            failed = self.state('throughout_failed',
                                f'{name} || (({active}) && !({self.guard}))')
            progress = f'({progress}) && !{failed}'
        declarations = [line for line in self.lines if line.startswith('reg ')]
        processes = [line for line in self.lines if not line.startswith('reg ')]
        return '\n'.join(declarations + processes + [f'(* keep *) wire {self.prefix} = {progress};', ''])


def emit(text, clock, prefix):
    parts = split(unwrap(text), r'\|->|\|=>')
    if len(parts) not in (1, 3):
        raise Unsupported('liveness_implication')
    monitor = Monitor(clock, prefix)
    request = monitor.expression(parts[0]) if len(parts) == 3 else '1'
    offset = int(len(parts) == 3 and parts[1] == '|=>')
    rhs = unwrap(parts[-1])
    request = monitor.delay(f'(({request}) != 0)', offset, 'start')[-1] if offset else request
    event = re.fullmatch(r's_eventually\s+(.+)', rhs, re.S)
    if event:
        pending = monitor.pending(request, monitor.expression(event[1]))
        return monitor.finish(f'!{pending}'), {}

    parts = split(rhs, r'\b(?:s_)?until(?:_with)?\b')
    if len(parts) > 1:
        if len(parts) != 3:
            raise Unsupported('liveness_until_association')
        left, operator, right = parts
        left, right = monitor.expression(left), monitor.expression(right)
        pending = monitor.pending(request, right)
        # Non-inclusive until does not require left at the completion sample.
        condition = f'({pending} || ({request})) && !({left})'
        if not operator.endswith('_with'):
            condition += f' && !({right})'
        fatal = monitor.fatal(condition)
        progress = f'!{fatal}' + (f' && !{pending}' if operator.startswith('s_') else '')
        return monitor.finish(progress), dict(operator=operator)

    # An assert/assume sequence property defaults to weak. Do not silently
    # strengthen an unbounded sequence into eventual completion.
    strength = 'weak'
    wrapper = re.match(r'(strong|weak)\s*\(', rhs)
    if wrapper:
        body, end = _group(rhs, wrapper.end()-1)
        if end != len(rhs):
            raise Unsupported('liveness_sequence_wrapper')
        strength, rhs = wrapper[1], unwrap(body)
    while True:
        first = re.match(r'first_match\s*\(', rhs)
        if first:
            body, end = _group(rhs, first.end()-1)
            if end != len(rhs):
                raise Unsupported('liveness_first_match_tail')
            rhs = unwrap(body)
            continue
        parts = split(rhs, r'\bthroughout\b')
        if len(parts) == 1:
            break
        if len(parts) != 3:
            raise Unsupported('liveness_throughout_association')
        guard = monitor.expression(parts[0])
        monitor.guard = f'({monitor.guard}) && ({guard})' if monitor.guard is not None else guard
        rhs = unwrap(parts[2])

    # Sequence builders retain parentheses around a repeated prefix. Remove
    # only that whole-prefix grouping, without changing its internal operators.
    completion = split(rhs, r'##\s*1\b')
    if len(completion) == 3:
        rhs = unwrap(completion[0]) + ' ##1 ' + completion[2]

    # One Boolean prefix followed by an unbounded delay and Boolean endpoint.
    delay = split(rhs, r'##\s*\[\s*\d+\s*:\s*\$\s*\]')
    if len(delay) == 3:
        initial = monitor.expression(delay[0]) if delay[0] else '1'
        response = monitor.expression(delay[2])
        minimum = int(re.search(r'\d+', delay[1])[0])
        taps = monitor.delay(f'(({request}) != 0)', minimum, 'eligible')
        eligible = taps[-1]
        fatal = monitor.fatal(f'({request}) && !({initial})')
        pending = monitor.pending(eligible, response)
        progress = f'!{fatal}' + (f' && !{pending}' if strength == 'strong' else '')
        return monitor.finish(progress, ' || '.join(taps+[pending])), dict(operator='unbounded_delay', minimum=minimum, strength=strength)

    # Consecutive repetition with no finite upper bound. An optional Boolean
    # completion is sampled one tick after the repeated segment.
    repeat = re.fullmatch(r'(.*?)\[\s*\*\s*(?:(\d+)\s*:\s*\$)?\s*\]\s*(?:##\s*1\s+(.+))?', rhs, re.S)
    if repeat:
        value = monitor.expression(repeat[1])
        minimum = int(repeat[2] or 0)
        if repeat[3] is None and minimum == 0:
            raise Unsupported('empty_sequence_property')
        response = monitor.expression(repeat[3]) if repeat[3] is not None else '1'
        taps = monitor.delay(f'(({request}) != 0)', minimum, 'mandatory')
        mandatory = ' || '.join(f'({tap})' for tap in taps[:-1]) or '0'
        eligible = taps[-1]
        pending = monitor.pending(eligible, response)
        fatal = monitor.fatal(f'(({mandatory}) && !({value})) || '
                              f'(({pending} || ({eligible})) && !({response}) && !({value}))')
        progress = f'!{fatal}' + (f' && !{pending}' if strength == 'strong' else '')
        return monitor.finish(progress, ' || '.join(taps+[pending])), dict(operator='unbounded_consecutive', minimum=minimum, strength=strength)

    # Literal goto/nonconsecutive counts. Count buckets retain overlapping
    # attempts. A separate owed set takes no new attempts until it empties.
    repeat = re.fullmatch(r'(.*?)\[\s*(->|=)\s*(\d+)(?:\s*:\s*(\d+))?\s*\]\s*(?:##\s*1\s+(.+))?', rhs, re.S)
    if repeat:
        value, operator, count = monitor.expression(repeat[1]), repeat[2], int(repeat[3])
        maximum = int(repeat[4] or repeat[3])
        completion = monitor.expression(repeat[5]) if repeat[5] is not None else None
        if not 1 <= count <= maximum <= LIMIT - bool(completion):
            raise Unsupported('liveness_capacity', 'repetition range must fit 64 state buckets')
        if maximum != count and completion is not None:
            return range_monitor(monitor, request, value, operator, count, maximum, completion, strength)
        width = count + bool(completion)
        active, owed = prefix+'_active', prefix+'_owed'
        truth = f'(({value}) != 0)'
        if completion is None:
            advance = lambda name: f'({truth} ? ({name} >> 1) : {name})'
            insert = f'(({request}) ? ({truth} ? {width}\'d{(1 << (count-1)) >> 1} : {width}\'d{1 << (count-1)}) : {width}\'d0)'
            fatal = None
        else:
            # Bit zero waits for completion. Higher bits count remaining events.
            # Goto ends at the Nth event; nonconsecutive can wait through !value.
            mask = (1 << width)-2
            wait = f'({active}[0])'
            invalid = f'{wait} && !({completion})' + (f' && {truth}' if operator == '=' else '')
            fatal = monitor.fatal(invalid)
            def advance(name):
                counting = f'({truth} ? (({name} & {width}\'d{mask}) >> 1) : ({name} & {width}\'d{mask}))'
                retain = f'(({name}[0] && !({completion}) && !{truth}) ? {width}\'d1 : {width}\'d0)' if operator == '=' else f'{width}\'d0'
                return f'({counting} | {retain})'
            insert = f'(({request}) ? ({truth} ? {width}\'d{1 << (count-1)} : {width}\'d{1 << count}) : {width}\'d0)'
        next_active = f'({advance(active)} | {insert})'
        monitor.state('active', next_active, width)
        monitor.state('owed', f'({owed} == 0) ? {next_active} : {advance(owed)}', width)
        progress = f'({owed} == 0)' if strength == 'strong' else '1\'b1'
        if fatal:
            progress = f'!{fatal} && ({progress})'
        return monitor.finish(progress, f'({active} != 0) || ({request})'), dict(operator='goto' if operator == '->' else 'nonconsecutive',
                                              count=count, strength=strength, completion=completion is not None,
                                              **(dict(maximum=maximum) if maximum != count else {}))
    raise Unsupported('liveness_form', rhs)


def range_monitor(monitor, request, value, operator, minimum, maximum, completion, strength):
    """Count occurrences per attempt and retain every permitted completion."""
    prefix, width = monitor.prefix, maximum+1
    active, owed = prefix+'_active', prefix+'_owed'
    truth = f'(({value}) != 0)'
    previous = monitor.state('previous_event', truth)
    eligible = ((1 << (maximum+1))-1) ^ ((1 << minimum)-1)
    # The target sample follows the last matched occurrence. Nonconsecutive
    # repetition can also end after trailing !value samples.
    complete = f'({completion})' + (f' && {previous}' if operator=='->' else '')
    upper = f'{active}[{maximum}]'
    invalid = f'{upper} && !({completion})' + (f' && {truth}' if operator=='=' else '')
    fatal = monitor.fatal(invalid)
    def advance(name):
        remaining = f'({name} & (({complete}) ? ~{width}\'d{eligible} : ~{width}\'d0))'
        return f'({truth} ? ({remaining} << 1) : {remaining})'
    born = f'(({request}) ? ({truth} ? {width}\'d2 : {width}\'d1) : {width}\'d0)'
    next_active = f'({advance(active)} | {born})'
    monitor.state('active', next_active, width)
    monitor.state('owed', f'({owed} == 0) ? {next_active} : {advance(owed)}', width)
    progress = f'!{fatal}' + (f' && ({owed} == 0)' if strength=='strong' else '')
    return monitor.finish(progress, f'({active} != 0) || ({request})'), dict(operator='goto' if operator=='->' else 'nonconsecutive',
                                          count=minimum, maximum=maximum, strength=strength, completion=True)
