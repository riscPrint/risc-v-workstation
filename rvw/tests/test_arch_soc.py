"""Topology parsing and connection tests. These do not run a simulator."""
from types import SimpleNamespace
import pytest
from test_arch_model import model, description
from test_arch import native_fixture


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


def test_soc_calibration_requires_matching_rtl(native_fixture, tmp_path):
    import json
    from rvw.arch import core
    description = native_fixture.parent / 'description.json'
    data = json.loads(description.read_text())
    data['soc'] = topology()
    description.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='matching RTL'):
        core.calibrate(native_fixture, 'fixture-0', tmp_path / 'refused')
    assert not (tmp_path / 'refused').exists()


def multi_topology():
    soc = topology()
    soc['memory'] = dict(kind='multi', interleave_bytes=64, controllers=[dict(kind='simple', latency='40ns', bandwidth='8GiB/s') for i in range(2)])
    soc['agents'] = [dict(start=0x81000000, size=4096, block_bytes=64,
        period_ticks=1000, duration_ticks=10000000, max_outstanding=4, attach=attach)
        for attach in ('memory', 'level2')]
    return soc


def test_multiple_controllers_and_agents(description):
    description['soc'] = multi_topology()
    model.validate_description(description)
    class Obj(SimpleNamespace):
        def __init__(self, *args, **kw):
            super().__init__(**kw)
            self.cpu_side_ports, self.mem_side_ports = object(), object()
    g = SimpleNamespace(**{key: Obj for key in ('SystemXBar', 'L2XBar', 'Cache',
        'SimpleMemory', 'MemCtrl', 'PyTrafficGen', 'AddrRange')})
    cpu = SimpleNamespace(createInterruptController=lambda: None, connectAllPorts=lambda *args: None)
    system = SimpleNamespace(mem_ranges=['RAM'])
    model.connect_memory(system, cpu, description, g, lambda cls, params: params)
    assert system.mem0.range.size == system.mem1.range.size == 2**29
    assert [system.mem0.range.intlvMatch, system.mem1.range.intlvMatch] == [0, 1]
    assert system.mem0.port is system.mem1.port is system.membus.mem_side_ports
    assert system.traffic0.port is system.membus.cpu_side_ports
    assert system.traffic1.port is system.level2bus.cpu_side_ports


@pytest.mark.parametrize('change', ['stripe', 'count', 'nested', 'agent_range', 'agent_attach', 'block'])
def test_invalid_multi_topology(description, change):
    soc = multi_topology()
    if change == 'stripe':
        soc['memory']['interleave_bytes'] = 65
    elif change == 'count':
        soc['memory']['controllers'].pop()
    elif change == 'nested':
        soc['memory']['controllers'][0] = soc['memory'].copy()
    elif change == 'agent_range':
        soc['agents'][0]['start'] = 0
    elif change == 'agent_attach':
        soc['agents'][0]['attach'] = 'level9'
    else:
        soc['agents'][0]['block_bytes'] = 3
    description['soc'] = soc
    with pytest.raises(ValueError):
        model.validate_description(description)
