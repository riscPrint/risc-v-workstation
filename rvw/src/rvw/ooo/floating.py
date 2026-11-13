"""Translate shared decoder register banks into timing dependency IDs."""


def operands(decoded, row):
    sources = tuple(register + (32 if bank == 'f' else 0) for bank, register in decoded.sources)
    if decoded.dest_bank == 'f':
        word = row['insn']
        if decoded.length == 4 or decoded.mnemonic.endswith('sp'):
            dest = word >> 7 & 31
        else:
            dest = 8 + (word >> 2 & 7)
        dest += 32
    else:
        dest = row['rd']
    kind = 'fp_' + decoded.mnemonic.split('.')[0] if decoded.cls == 'float' else decoded.cls
    return kind, sources, dest
