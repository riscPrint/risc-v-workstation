"""Ordered eventual Boolean milestones with overlapping obligations."""
from .temporal import Unsupported, split, unwrap


def milestones(text):
    """Accept F(a && F(b && F(c))), without imposing a finite deadline."""
    text = unwrap(text)
    if not text.startswith('s_eventually '):
        return None
    body = unwrap(text[len('s_eventually '):])
    if body.startswith('s_eventually '):
        rest = milestones(body)
        return ['1'] + rest
    parts = split(body, r'&&')
    if len(parts) >= 3 and unwrap(parts[-1]).startswith('s_eventually '):
        rest = milestones(parts[-1])
        return [' && '.join(parts[::2][:-1])] + rest
    return [body]


def emit(monitor, request, terms):
    if not 2 <= len(terms) <= 8:
        raise Unsupported('nested_eventually_capacity', 'two to eight Boolean milestones')
    terms = [monitor.expression(term) for term in terms]
    width = len(terms)
    active, owed = monitor.prefix + '_active', monitor.prefix + '_owed'

    def advance(state, incoming):
        bits = []
        for index, term in enumerate(terms):
            waiting = f'({state}[{index}] || ({incoming}))'
            bits.append(f'({waiting} && !({term}))')
            incoming = f'({waiting} && ({term}))'
        return '{' + ', '.join(reversed(bits)) + '}'

    next_active = advance(active, request)
    monitor.state('active', next_active, width)
    monitor.state('owed', f'({owed} == 0) ? {next_active} : {advance(owed, "0")}', width)
    return monitor.finish(f'({owed} == 0)'), dict(operator='nested_eventually', milestones=width)
