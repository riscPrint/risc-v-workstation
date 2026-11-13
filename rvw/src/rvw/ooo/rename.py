"""Bounded integer rename elimination and LUI/AUIPC+ADDI issue fusion."""


def validate(policy):
    if not isinstance(policy, dict) or set(policy) - {'move_elimination', 'zero_elimination', 'immediate_fusion'}:
        raise ValueError('invalid rename policy')
    if any(type(v) is not bool for v in policy.values()):
        raise ValueError('rename policy flags must be booleans')


def elimination(op, policy):
    if op.kind != 'alu' or not op.dest:
        return None
    word = op.encoding
    zero = op.mnemonic in ('xor', 'sub') and len(op.sources) == 2 and op.sources[0] == op.sources[1]
    move = (op.mnemonic == 'addi' and word >> 20 == 0) or op.mnemonic == 'c.mv'
    if op.mnemonic in ('add', 'or') and 0 in op.sources:
        move = True
    if move and not any(op.sources):
        zero = True
    if zero and policy.get('zero_elimination'):
        return 'zero'
    if move and policy.get('move_elimination'):
        return 'move'
    return None


def fuses(previous, current, policy):
    return bool(policy.get('immediate_fusion') and previous is not None and
                previous.mnemonic in ('lui', 'auipc') and current.mnemonic == 'addi' and
                previous.dest and previous.dest == current.dest and current.sources == (previous.dest,) and
                current.pc == previous.pc + previous.length)
