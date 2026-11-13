"""Clock-local sampled values with finite history and four-state comparisons."""
import re

from .sva import _expression, _group

LIMIT = 64
PATTERN = re.compile(r'\$(past|rose|fell|stable|changed)\s*\(')


def arguments(body, kind):
    from .temporal import Unsupported, split
    args = split(body, r',')
    depth = 1
    if len(args) > 1:
        if kind != 'past' or len(args) != 3:
            raise Unsupported('sampled_arguments')
        if not args[2].isdecimal() or not 1 <= int(args[2]) <= LIMIT:
            raise Unsupported('sampled_depth', args[2])
        depth = int(args[2])
    return args[0], depth


def validate(expression, level=0):
    from .temporal import Unsupported
    if level > 8:
        raise Unsupported('sampled_nesting_limit')
    output, start = '', 0
    while match := PATTERN.search(expression, start):
        body, end = _group(expression, match.end()-1)
        body, _ = arguments(body, match[1])
        validate(body, level+1)
        output += expression[start:match.start()] + 'rvw_sampled_value'
        start = end
    output += expression[start:]
    if '$' in output:
        raise Unsupported('sampled_function', output)
    _expression(output)


def emit(expression, clock, prefix, level=0):
    if level == 0:
        validate(expression)
    lines, output, start, count = [], '', 0, 0
    while match := PATTERN.search(expression, start):
        body, end = _group(expression, match.end()-1)
        kind = match[1]
        body, depth = arguments(body, kind)
        name = f'{prefix}_{count}'
        count += 1
        body, nested = emit(body, clock, name + '_nested', level+1)
        lines.extend(nested)
        lines.append(f'wire [$bits({body})-1:0] {name}_now = ({body});')
        previous = f'{name}_now'
        for index in range(depth):
            stage = f'{name}_old{index}'
            lines += [f'reg [$bits({body})-1:0] {stage};',
                      f'always @(posedge {clock}) {stage} <= {previous};']
            previous = stage
        # The storage is a bit vector. Restore the source expression's width
        # and signedness at use. Its current bits are masked to a typed zero.
        zero = '$signed({$bits(' + body + "){1'b0}})"
        past = f'($signed({previous}) | (({body}) & {zero}))'
        value = {'past': past,
                 'rose': f'(({name}_now[0] === 1\'b1) && ({previous}[0] !== 1\'b1))',
                 'fell': f'(({name}_now[0] === 1\'b0) && ({previous}[0] !== 1\'b0))',
                 'stable': f'({name}_now === {previous})',
                 'changed': f'({name}_now !== {previous})'}[kind]
        output += expression[start:match.start()] + value
        start = end
    output += expression[start:]
    return output, lines
