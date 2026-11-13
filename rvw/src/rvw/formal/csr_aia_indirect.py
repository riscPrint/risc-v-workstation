"""Bounded IMSIC indirect-register oracle with explicit unknown initial state.

The caller supplies accepted transactions and the selected guest file. This is
not a privilege/virtual-instruction, priority-arbitration or delivery model.
"""
from dataclasses import dataclass


class UnsupportedSelection(ValueError):
    """No model for this selection. Do not convert this into a DUT trap pass."""


@dataclass(frozen=True)
class Expectation:
    value: int
    known_mask: int
    width: int

    def compare(self, observed):
        if (observed ^ self.value) & self.known_mask:
            return 'mismatch'
        return 'match' if self.known_mask == (1 << self.width) - 1 else 'inconclusive'


class ImsicIndirectModel:
    def __init__(self, xlen=32, identities=63, guests=0):
        if xlen not in (32,64) or not 63 <= identities <= 2047 or (identities+1) % 64 or not 0 <= guests <= 63:
            raise ValueError('declare XLEN, 64k-1 identities and bounded guest files')
        self.xlen, self.identities, self.guests = xlen, identities, guests
        self.selectors = {'M':0, 'S':0, 'VS':0}
        self.state = {}
        self.word_mask = (1 << xlen)-1

    def select(self, context, value):
        if context not in self.selectors or type(value) is not int or value < 0:
            raise ValueError('invalid selector write')
        # Project WARL policy: retain the required low 8/9-bit selector range.
        self.selectors[context] = value & (0xff if context == 'M' else 0x1ff)

    def _target(self, context, guest):
        if context not in self.selectors:
            raise ValueError('unknown CSR context')
        file = context
        if context == 'VS':
            if not 1 <= guest <= self.guests:
                raise UnsupportedSelection('guest file absent; no access-fault model')
            file = f'VS{guest}'
        selector = self.selectors[context]
        if selector == 0x70:
            return (file,selector),1
        if selector == 0x72:
            return (file,selector),(1 << self.identities.bit_length())-1
        base = 0x80 if 0x80 <= selector <= 0xbf else 0xc0 if 0xc0 <= selector <= 0xff else None
        if base is None or self.xlen == 64 and (selector-base) % 2:
            raise UnsupportedSelection('unsupported or RV64 odd indirect selection')
        first = 32*(selector-base)
        if first > self.identities:
            raise UnsupportedSelection('register beyond modeled identity capacity')
        implemented = ((1 << min(self.xlen,self.identities-first+1))-1) << first
        implemented &= ~1
        return (file,selector),(implemented >> first) & self.word_mask

    def read(self, context, guest=0):
        key,mask = self._target(context,guest)
        value,known = self.state.get(key,(0,0))
        return Expectation(value & mask,known | (self.word_mask ^ mask),self.xlen)

    def write(self, context, data, guest=0):
        key,mask = self._target(context,guest)
        if type(data) is not int or not 0 <= data <= self.word_mask:
            raise ValueError('write data exceeds XLEN')
        selector = self.selectors[context]
        if selector == 0x70 and data not in (0,1) or selector == 0x72 and data > self.identities:
            raise UnsupportedSelection('declare a project legalization for this control value')
        self.state[key] = data & mask, self.word_mask

    def msi(self, file, identity):
        if file not in ['M','S',*[f'VS{i}' for i in range(1,self.guests+1)]]:
            raise ValueError('unknown interrupt file')
        if not 1 <= identity <= self.identities:
            return  # Invalid MSI identity has no effect.
        selector = 0x80 + (identity // self.xlen)*(self.xlen//32)
        bit = 1 << (identity % self.xlen)
        key = file,selector
        value,known = self.state.get(key,(0,0))
        self.state[key] = value | bit, known | bit
