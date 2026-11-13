"""Bind a project module's declared ports to the datapath reference interface."""
from .common import check_ident


def bind(design, spec):
    top = spec['top']
    check_ident('binding top', top)
    module = design['modules'][top]
    aliases = spec['ports']
    canonical = {'clk', 'reset', 'start', 'done', 'a', 'b', 'c', 'rm', 'y', 'flags'}
    if not isinstance(aliases, dict) or not set(aliases) <= canonical:
        raise ValueError('binding ports must use canonical datapath names')
    for name in aliases.values():
        check_ident('binding port', name)
    if len(set(aliases.values())) != len(aliases) or set(aliases.values()) - set(module['ports']):
        raise ValueError('binding needs distinct existing ports')
    inverse = {actual: name for name, actual in aliases.items()}
    ports = {inverse.get(name, name): port for name, port in module['ports'].items()}
    if len(ports) != len(module['ports']):
        raise ValueError('binding port names collide')
    # The translator checks every port, bit width, state cell and driver after
    # this rename. No port is hidden or tied by a binding.
    return {'modules': {'dut': {**module, 'ports': ports}}}
