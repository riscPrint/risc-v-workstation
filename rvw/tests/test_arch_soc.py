"""Topology parsing and connection tests. These do not run a simulator."""
from types import SimpleNamespace
import pytest
from test_arch_model import model, description


def topology():
    return {'levels': [{'size': '256KiB', 'assoc': 8}, {'size': '2MiB', 'assoc': 16}],
            'interconnect': dict(width=16, frontend_latency=1, forward_latency=2,
                                 response_latency=1, snoop_response_latency=1),
            'memory': dict(kind='dram', model='DDR4_2400_8x8', controller={}, interface={})}


@pytest.mark.parametrize('levels', [0, 1, 2])
@pytest.mark.parametrize('dram', [False, True])
def test_serial_connections(description, levels, dram):
    soc = topology()
    soc['levels'] = soc['levels'][:levels]
    if not dram:
        soc['memory'] = dict(kind='simple', latency='40ns', bandwidth='8GiB/s')
    description['soc'] = soc
    model.validate_description(description)
    class Obj(SimpleNamespace):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.cpu_side_ports = object()
            self.mem_side_ports = object()
    g = SimpleNamespace(**{key: Obj for key in
        ('SystemXBar', 'L2XBar', 'Cache', 'SimpleMemory', 'MemCtrl', 'DDR4_2400_8x8')})
    calls = []
    cpu = SimpleNamespace(createInterruptController=lambda: None,
                          connectAllPorts=lambda *args: calls.append(args))
    system = SimpleNamespace(mem_ranges=['RAM'])
    model.connect_memory(system, cpu, description, g, lambda cls, params: params)
    assert system.mem.port is system.membus.mem_side_ports
    assert calls[0][0] is (system.level2bus if levels else system.membus).cpu_side_ports
    if levels:
        assert system.level2.cpu_side is system.level2bus.mem_side_ports
        target = system.level3bus if levels == 2 else system.membus
        assert system.level2.mem_side is target.cpu_side_ports
    if dram:
        assert system.mem.dram.range == 'RAM'
    else:
        assert system.mem.latency == '40ns'


@pytest.mark.parametrize('key,value', [('levels', [{}, {}, {}]), ('levels', [{}]),
    ('interconnect', {'width': 16}), ('memory', {'kind': 'unknown'}),
    ('memory', dict(kind='dram', model='BadAddr', controller={}, interface={}))])
def test_invalid_topology(description, key, value):
    soc = topology()
    soc[key] = value
    description['soc'] = soc
    with pytest.raises(ValueError):
        model.validate_description(description)
