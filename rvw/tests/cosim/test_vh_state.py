import copy
import pytest
from rvw.cosim.extensions import header_fields, state_fields, compare_extensions, H_CSRS


def header():
    return dict(schema='rvw.rvfi/2', xlen=64, isa='rv64imafdcvh_zicsr',
                vector=dict(vlen=128, elen=64), hypervisor=True)


def state():
    return dict(mode=3, vector=dict(vstart='0x0', vl='0x4', vtype='0x10',
                vcsr='0x0', vs='0x3', regs=['0x0']*32),
                hypervisor=dict(virtual=False, mode_after=3, virtual_after=False,
                csrs={hex(a): '0x0' for a in H_CSRS}, translations=[]))


@pytest.mark.parametrize('field', ['vl', 'vtype', 'vstart', 'vcsr', 'vs', 'regs'])
def test_vector_mutations(field):
    h, a = header(), state()
    state_fields(a, h)
    e = copy.deepcopy(a)
    if field == 'regs':
        a['vector'][field][0] = 1  # mask mutation
    else:
        a['vector'][field] ^= 1
    assert 'vector.'+field in compare_extensions(a, e, h)


@pytest.mark.parametrize('field', ['virtual', 'mode_after', 'virtual_after', 'csrs'])
def test_h_mutations(field):
    h, a = header(), state()
    state_fields(a, h)
    e = copy.deepcopy(a)
    if field == 'csrs':
        a['hypervisor'][field]['0x643'] = 1
    else:
        a['hypervisor'][field] = 1
    assert 'hypervisor.'+field in compare_extensions(a, e, h)


@pytest.mark.parametrize('field', ['vector', 'hypervisor'])
def test_partial_state(field):
    a = state()
    del a[field]
    with pytest.raises(ValueError):
        state_fields(a, header())
    h = header()
    del h[field]
    with pytest.raises(ValueError):
        header_fields(h)


@pytest.mark.parametrize('vlen,elen', [(127,64), (128,128), (64,64), (128,0), (True,64)])
def test_bad_dimensions(vlen, elen):
    h = header()
    h['vector'] = dict(vlen=vlen, elen=elen)
    with pytest.raises(ValueError):
        header_fields(h)


def test_reference_missing_state():
    with pytest.raises(ValueError, match='reference cannot check'):
        compare_extensions(state(), {}, header())


def native_trace(tmp_path, tmp_path_factory, kind):
    from pathlib import Path
    from cosim_build import _build
    from model_fixtures import generate, Spike
    from rvw.cosim.platform import Platform
    import json
    isa = 'rv64imafdcv_zicsr' if kind == 'vector' else 'rv64imafdch_zicsr'
    elf = _build(tmp_path_factory, Path(__file__).with_name('program_'+kind+'.S'), march=isa)
    platform = Platform('reference', 64, isa, 0x80000000, [(0x80000000, 0x1000000)], [])
    trace = tmp_path / (kind+'.jsonl')
    generate(elf, trace, platform, limit=100)
    return trace, elf, platform, Spike


@pytest.mark.parametrize('kind', ['vector', 'hypervisor'])
def test_spike_only_state(tmp_path, tmp_path_factory, kind):
    import json
    from rvw.cosim.checker import check
    trace, elf, p, Spike = native_trace(tmp_path, tmp_path_factory, kind)
    lines = [json.loads(s) for s in trace.read_text().splitlines()]
    rows = [s for s in lines[1:] if 'event' not in s]
    if kind == 'vector':
        assert int(rows[-1]['vector']['regs'][3], 16) & ((1 << 128)-1) == sum(v << (32*i) for i,v in enumerate([9,9,9,9]))
        assert any(int(r['vector']['vstart'], 16) == 1 for r in rows)
        assert int(rows[-1]['vector']['vstart'], 16) == 0
        assert any(r['trap'] for r in rows)  # pinned Spike rejects nonzero vstart for ALU
        assert int(rows[-1]['vector']['regs'][0], 16) & 15 == 15
    else:
        assert any(r['hypervisor']['virtual'] and r['mode'] == 1 for r in rows)
        assert any(r['hypervisor']['virtual'] and not r['hypervisor']['virtual_after'] for r in rows)
        assert int(rows[-1]['hypervisor']['csrs']['0x142'], 16) == 10
        assert int(rows[-1]['hypervisor']['csrs']['0x600'], 16) & (1 << 7)  # SPV
    model = Spike(p, elf)
    try:
        assert check(trace, model, p, sync=())['status'] == 'match'
    finally:
        model.close()
    if kind == 'vector':
        rows[-1]['vector']['regs'][0] = hex(int(rows[-1]['vector']['regs'][0],16)^1)
    else:
        rows[-1]['hypervisor']['csrs']['0x643'] = '0x1'
    trace.write_text('\n'.join(map(json.dumps, lines))+'\n')
    model = Spike(p, elf)
    try:
        assert check(trace, model, p, sync=())['status'] == 'mismatch'
    finally:
        model.close()


def test_spike_only_two_stage(tmp_path, tmp_path_factory):
    from pathlib import Path
    from cosim_build import _build
    from model_fixtures import Spike
    from rvw.cosim.platform import Platform
    from rvw.cosim.checker import check
    from rvw.cosim.trace import record
    from rvw.cosim.extensions import serialize
    import json
    p = Platform('reference', 64, 'rv64imafdch_zicsr', 0x80000000, [(0x80000000, 0x1000000)], [])
    elf = _build(tmp_path_factory, Path(__file__).with_name('program_hypervisor_walk.S'), march=p.isa)
    model = Spike(p, elf)
    rows = [dict(schema='rvw.rvfi/2', xlen=64, isa=p.isa, core='reference', config='reference', elf=str(elf), hypervisor=True)]
    try:
        for i in range(100):
            e = model.step()
            if e['hypervisor']['virtual'] and not e['trap']:
                e['hypervisor']['translations'] = model.translations(e)
                t = e['hypervisor']['translations'][0]
                assert t['gpa'] == t['va']+0x40000000
                assert t['pa'] == t['va']
            r = record(e, i)
            r.update(fd_valid=bool(e['fd_valid']), fd=e['fd'], fd_wdata=hex(e['fd_wdata']), fflags=hex(e['fflags']), fcsr=hex(e['fcsr']), hypervisor=serialize(e['hypervisor']))
            r['hypervisor']['mode_after'] = e['hypervisor']['mode_after']
            rows.append(r)
            if e['halted'] or e['trap']:
                break
    finally:
        model.close()
    translated = [r for r in rows[1:] if r['hypervisor']['translations']]
    assert translated
    trace = tmp_path / 'walk.jsonl'
    trace.write_text('\n'.join(map(json.dumps, rows))+'\n')
    model = Spike(p, elf)
    try:
        result = check(trace, model, p, sync=())
        assert result['status'] == 'match'
        assert result['state_coverage']['two_stage_translations'] == len(translated)
    finally:
        model.close()
    translated[0]['hypervisor']['translations'][0]['gpa'] = '0x0'
    trace.write_text('\n'.join(map(json.dumps, rows))+'\n')
    model = Spike(p, elf)
    try:
        assert 'hypervisor.translations' in check(trace, model, p, sync=())['mismatch']['differences']
    finally:
        model.close()


@pytest.mark.parametrize('field', ['vstart', 'vl', 'vtype', 'vcsr', 'vs', 'regs'])
def test_partial_vector_fields_refused(field):
    a = state()
    del a['vector'][field]
    with pytest.raises(ValueError, match='partial vector'):
        state_fields(a, header())


def test_v1_vector_cannot_match_integer_only():
    h = header()
    h['schema'] = 'rvw.rvfi/1'
    with pytest.raises(ValueError, match='requires C2/2'):
        header_fields(h)


def test_translation_state_validates_all_addresses():
    a = state()
    a['hypervisor']['translations'] = [dict(va='0x1', gpa='0x2', pa='unknown', access='load')]
    with pytest.raises(ValueError, match='hex string'):
        state_fields(a, header())


@pytest.mark.parametrize('letter', ['v', 'h'])
def test_reference_isa_cannot_hide_extension_state(letter):
    from rvw.cosim.platform import Platform
    from rvw.cosim.spike import Spike
    p = Platform('reference', 64, 'rv64imafdc_zicsr', 0x80000000, [(0x80000000, 4096)], [],
                 reference_isa='rv64imafdc'+letter+'_zicsr')
    with pytest.raises(ValueError, match='preserve V/H'):
        Spike(p, 'unused.elf', shim=None)
