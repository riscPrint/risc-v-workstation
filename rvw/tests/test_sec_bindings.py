"""SoC-map memory regions and catalog CSR resolution for flow tracking."""
import json
import pytest
from rvw.sec import bindings

pytestmark = pytest.mark.fast

SOC = dict(schema='rvw.soc/1', name='t', address_bits=32, platform=dict(name='t', xlen=32),
           regions=[dict(name='ram', kind='ram', base='0x80000000', size='0x8000', permissions='rwx',
                         cacheable=False, registers=[]),
                    dict(name='keys', kind='ram', base='0x80008000', size='0x100', permissions='rw',
                         cacheable=False, registers=[]),
                    dict(name='aes', kind='mmio', base='0x10000000', size='0x1000', permissions='rw',
                         cacheable=False, registers=[dict(name='key0', offset='0x10', width=32, access='rw',
                                                          reset=0, read_action='none', write_action='normal')])],
           interrupts=[])


def test_soc_regions_resolve(tmp_path):
    (tmp_path/'soc.json').write_text(json.dumps(SOC))
    policy = dict(memory_regions=[dict(soc_region='keys'), dict(soc_region='keys', offset='0x10', size=8),
                                  dict(soc_region='aes', register='key0'), dict(symbol='secret', size=4)])
    out = bindings.memory(policy, tmp_path/'soc.json')
    assert out[0] == dict(base='0x80008000', size='0x100', soc_region='keys')
    assert out[1]['base'] == '0x80008010' and out[1]['size'] == '0x8'
    assert out[2] == dict(base='0x10000010', size='0x4', soc_region='aes', register='key0')
    assert out[3] == dict(symbol='secret', size=4)
    with pytest.raises(ValueError, match='no region nope'):
        bindings.memory(dict(memory_regions=[dict(soc_region='nope')]), tmp_path/'soc.json')
    with pytest.raises(ValueError, match='exceeds'):
        bindings.memory(dict(memory_regions=[dict(soc_region='keys', offset='0xf0', size=32)]), tmp_path/'soc.json')
    with pytest.raises(ValueError, match='needs a SoC map'):
        bindings.memory(dict(memory_regions=[dict(soc_region='keys')]), None)


def test_csr_names_resolve_to_one_storage_signal():
    nets = ['CsrPlugin_mscratch', '$0\\CsrPlugin_mscratch[31:0]', 'CsrPlugin_mepc', 'x_mepc_value', 'other']
    assert bindings.csr_signals(['mscratch', 0x340], nets) == {'mscratch': 'CsrPlugin_mscratch'}
    with pytest.raises(ValueError, match='ambiguous signals CsrPlugin_mepc, x_mepc_value'):
        bindings.csr_signals(['mepc'], nets)
    assert bindings.csr_signals(['mepc'], nets, {'mepc': 'CsrPlugin_mepc'}) == {'mepc': 'CsrPlugin_mepc'}
    assert bindings.csr_signals(['mepc'], nets, registers={'CsrPlugin_mepc'}) == {'mepc': 'CsrPlugin_mepc'}
    assert bindings.csr_signals(['mscratch'], nets+['snapshot_mscratch'], registers={'CsrPlugin_mscratch', 'snapshot_mscratch'},
                                ports={'snapshot_mscratch'}) == {'mscratch': 'CsrPlugin_mscratch'}
    with pytest.raises(ValueError, match='no storage signal'):
        bindings.csr_signals(['mtval'], nets)
    with pytest.raises(ValueError, match='not in the pinned CSR catalog'):
        bindings.csr_signals(['notacsr'], nets)
    with pytest.raises(ValueError, match='not in the design'):
        bindings.csr_signals(['mepc'], nets, {'mepc': 'missing'})
