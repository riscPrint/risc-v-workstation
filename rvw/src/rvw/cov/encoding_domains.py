"""Finite encoded field domains. Encoded bits do not infer register-bank values."""
import re

SMALL_FIELDS = frozenset(('rm','aq','rl','aqrl','vm','nf','wd','mop','lumop','sumop','simm5','zimm5','zimm','csr'))


def domain(argument, high, low):
    width=high-low+1
    register=bool(re.fullmatch(r'(?:rd|rs[123]|vd|vs[123])(?:_[a-z0-9]+)*',argument))
    if register and 1 <= width <= 5:
        return list(range(1<<width))
    if argument in SMALL_FIELDS and 1 <= width <= 6:
        return list(range(1<<width))
    return None
