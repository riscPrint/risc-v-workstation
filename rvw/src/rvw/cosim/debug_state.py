"""Debug state is separate from ordinary trap entry."""
from .trace import hexnum


def validate(state, xlen):
    if not isinstance(state, dict) or set(state) != {'mode', 'dpc', 'dcsr', 'step'}:
        raise ValueError('debug state requires mode, dpc, dcsr and step')
    if type(state['mode']) is not bool or type(state['step']) is not bool:
        raise ValueError('debug mode and step must be boolean')
    state['dpc'] = hexnum(state['dpc'], xlen)
    state['dcsr'] = hexnum(state['dcsr'], 32)
    if state['step'] != bool(state['dcsr'] & 4):
        raise ValueError('debug step disagrees with dcsr.step')
    return state


def differences(actual, expected):
    return {f'debug.{k}': {'expected': expected[k], 'actual': v}
            for k, v in actual.items() if v != expected[k]}
