"""Disjoint integer operand prefixes for bounded datapath proof jobs."""


def partition(width, bits, index):
    if bits is None and index is None:
        return None
    if type(bits) is not int or not 1 <= bits <= width or type(index) is not int or not 0 <= index < 2**bits:
        raise ValueError('operand partition needs bits in 1..width and index in 0..2**bits-1')
    shift = width - bits
    return dict(operand='b', bits=bits, index=index, parts=2**bits,
                lower=index << shift, upper=((index+1) << shift)-1,
                complete_domain=False)


def constrain(case):
    if case is None:
        return ''
    # Substitution propagates fixed prefix bits before SAT construction. Remaining
    # low bits retain their full domain. No reference or RTL equations change.
    low_mask = case['upper'] - case['lower']
    return f'b = (b & {low_mask}ULL) | {case["lower"]}ULL;\n'
