"""Check sampled reset state against a caller-supplied project contract.

The caller must capture these observations from the DUT. Model construction is
not a reset observation. This API does not assert a reset or reload memory.
"""
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ResetContract:
    state: Mapping[str, tuple[int, int]]  # expected value, comparison mask
    invalid_outputs: tuple[str, ...]


@dataclass(frozen=True)
class ResetSample:
    cycle: int
    asserted: bool
    state: Mapping[str, int | None]
    valid: Mapping[str, bool | None]


def check_reset(contract: ResetContract, samples: Sequence[ResetSample]):
    """Check one actual assertion/release pulse. Return no vacuous success.

    Samples start while reset is asserted and end at the contract's state-check
    boundary after release. The caller selects that boundary before the run.
    Unknown state is inconclusive. A measured conflict takes precedence.
    """
    if not contract.state or not contract.invalid_outputs:
        return {'status': 'inconclusive', 'reason': 'missing project reset contract'}
    if len(samples) < 2 or not samples[0].asserted or samples[-1].asserted:
        return {'status': 'inconclusive', 'reason': 'missing assertion or release observation'}
    if any(a.cycle >= b.cycle for a, b in zip(samples, samples[1:])):
        raise ValueError('reset sample cycles must increase')
    if any(s.asserted for s in samples[next(i for i,s in enumerate(samples) if not s.asserted):]):
        raise ValueError('check each reset pulse separately')
    unknown = False
    for sample in samples:
        if sample.asserted:
            for name in contract.invalid_outputs:
                value = sample.valid.get(name)
                if value is True:
                    return {'status': 'mismatch', 'reason': f'valid output during reset: {name}'}
                if value is not False:
                    unknown = True
    for name, (expected, mask) in contract.state.items():
        if mask <= 0 or expected < 0:
            raise ValueError('reset state needs a positive mask and nonnegative expected value')
        value = samples[-1].state.get(name)
        if value is None:
            unknown = True
        elif (value ^ expected) & mask:
            return {'status': 'mismatch', 'reason': f'reset state differs: {name}'}
    return {'status': 'inconclusive' if unknown else 'consistent',
            'reason': 'missing sampled values' if unknown else 'sampled reset contract checked'}
