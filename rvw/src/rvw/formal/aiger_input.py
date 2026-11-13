"""Read finite AIGER safety models without dropping bad states or constraints."""


def to_verilog(data, top):
    pos = 0
    def line():
        nonlocal pos
        end = data.find(b'\n', pos)
        if end < 0:
            raise ValueError('truncated AIGER line')
        result = data[pos:end].decode('ascii')
        pos = end + 1
        return result
    header = line().split()
    if not header or header[0] not in ('aig', 'aag') or not 6 <= len(header) <= 10:
        raise ValueError('invalid AIGER header')
    binary = header[0] == 'aig'
    counts = list(map(int, header[1:]))
    counts += [0] * (9 - len(counts))
    m, ni, nl, no, na, nb, nc, nj, nf = counts
    if any(n < 0 for n in counts) or nj or nf:
        raise ValueError('only finite AIGER safety models are supported; no justice/fairness')
    if m < ni + nl + na or (binary and m != ni + nl + na):
        raise ValueError('invalid AIGER variable count')
    inputs = [2 * (i + 1) for i in range(ni)] if binary else [int(line()) for _ in range(ni)]
    latches = []
    for i in range(nl):
        values = list(map(int, line().split()))
        if binary:
            current = 2 * (ni + i + 1)
        else:
            if len(values) < 2:
                raise ValueError('invalid AIGER latch')
            current = values.pop(0)
        if len(values) not in (1, 2):
            raise ValueError('invalid AIGER latch')
        nxt, init = values[0], values[1] if len(values) == 2 else 0
        if init not in (0, 1, current):
            raise ValueError('invalid AIGER latch initialization')
        latches.append((current, nxt, init))
    outputs = [int(line()) for _ in range(no)]
    bad = [int(line()) for _ in range(nb)]
    constraints = [int(line()) for _ in range(nc)]
    # Legacy competition models use outputs as bad-state predicates.
    if no and nb:
        raise ValueError('mixed ordinary outputs and bad-state predicates need an explicit export')
    bad = bad or outputs
    if not bad:
        raise ValueError('AIGER has no safety properties')
    gates = []
    def varint():
        nonlocal pos
        value, shift = 0, 0
        while True:
            if pos >= len(data) or shift > 63:
                raise ValueError('invalid AIGER delta encoding')
            byte = data[pos]
            pos += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
            shift += 7
    for i in range(na):
        if binary:
            lhs = 2 * (ni + nl + i + 1)
            a = lhs - varint()
            b = a - varint()
        else:
            values = list(map(int, line().split()))
            if len(values) != 3:
                raise ValueError('invalid AIGER AND')
            lhs, a, b = values
        if lhs % 2 or lhs <= 1 or not 0 <= a < lhs or not 0 <= b < lhs:
            raise ValueError('invalid AIGER gate dependency')
        gates.append((lhs, a, b))
    defined = {0}
    for literal in inputs + [c for c, _, _ in latches] + [c for c, _, _ in gates]:
        if literal % 2 or not 0 < literal <= 2 * m or literal // 2 in defined:
            raise ValueError('duplicate or invalid AIGER variable')
        defined.add(literal // 2)
    refs = bad + constraints + [n for _, n, _ in latches] + [x for _, a, b in gates for x in (a, b)]
    if any(x < 0 or x // 2 not in defined for x in refs):
        raise ValueError('undefined AIGER literal')
    def expr(literal):
        if literal < 2:
            return "1'b" + str(literal)
        return ('~' if literal % 2 else '') + f'n{literal // 2}'
    lines = [f'module {top}(' + ', '.join(f'input n{x // 2}' for x in inputs) + ');']
    for cur, nxt, init in latches:
        lines.append(f'reg n{cur // 2};')
        if init in (0, 1):
            lines.append(f"initial n{cur // 2} = 1'b{init};")
        lines.append(f'always @($global_clock) n{cur // 2} <= {expr(nxt)};')
    for lhs, a, b in gates:
        lines.append(f'wire n{lhs // 2} = {expr(a)} & {expr(b)};')
    for literal in constraints:
        lines.append(f'always @* assume({expr(literal)});')
    for literal in bad:
        lines.append(f'always @* assert(!({expr(literal)}));')
    return '\n'.join(lines) + '\nendmodule\n'
