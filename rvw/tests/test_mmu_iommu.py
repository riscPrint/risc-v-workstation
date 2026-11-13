import pytest
from rvw.regress.mmu_iommu import Model, device_agent, UPSTREAM


pytestmark = pytest.mark.fast


def test_device_process_fault_queue():
    model = Model({1: {'processes': {2: {'mode': 'bare'}}}}, {}, queue_size=2)
    request = dict(device=1, process=2, address=0x1234, access='load')
    assert model.translate(request)['pa'] == 0x1234
    fault = model.translate(dict(request, process=3))
    assert fault['status'] == 'fault' and fault['stage'] == 'process'
    model.translate(dict(request, device=2))
    assert len(model.faults) == 1 and model.overflow
    assert model.faults.popleft() == {k: v for k, v in fault.items() if k != 'status'}
    assert len(UPSTREAM['revision']) == 40


def test_msi_and_command_queue():
    model = Model({1: {'msi': dict(mask=0xffff0000, pattern=0x24000000, pages={0x24000: 0x28000000})}}, {}, queue_size=4)
    request = dict(device=1, address=0x24000004, access='store')
    assert model.translate(request)['pa'] == 0x28000004
    model.contexts[1]['msi']['pages'][0x24000] = 0x30000000
    assert model.translate(request)['pa'] == 0x28000004
    model.enqueue(dict(op='iotinval', device=1))
    model.enqueue(dict(op='iofence'))
    assert model.fence_sequence == 0
    model.process_command()
    assert model.translate(request)['pa'] == 0x30000004
    assert model.process_command() == dict(status='completed', sequence=1)
    assert model.process_command() is None


def test_agent_needs_independent_response():
    request = dict(device=1, address=0x1000, access='load')
    assert device_agent(Model({1: {}}, {}), [request], lambda r: None)['status'] == 'inconclusive'
    assert device_agent(Model({1: {}}, {}), [request], lambda r: dict(status='translated', pa=0x2000))['status'] == 'mismatch'
    assert device_agent(Model({1: {}}, {}), [request], lambda r: dict(status='translated', pa=0x1000))['status'] == 'consistent'
    assert device_agent(Model({1: {}}, {}), [], lambda r: None)['status'] == 'inconclusive'


def test_command_capacity():
    model = Model({}, {}, queue_size=2)
    model.enqueue(dict(op='iofence'))
    with pytest.raises(ValueError, match='full'):
        model.enqueue(dict(op='iofence'))


def test_first_second_stage_isolation_and_invalidation():
    from rvw.regress.mmu_paging import page_tables
    from rvw.regress.mmu import ROOT, DATA
    pages, leaf = page_tables(dict(mode='sv39', level=0), ROOT, DATA, 0xdf)
    memory = {ROOT + d * 4096 + i * 8: p for d, table in enumerate(pages) for i, p in enumerate(table)}
    g_root = 0x80020000
    memory[g_root + 2 * 8] = (0x80000000 >> 12 << 10) | 0xdf
    memory[g_root + 16384 + 2 * 8] = 0
    first, second = dict(mode='sv39', root=ROOT), dict(mode='sv39', root=g_root)
    model = Model({1: dict(first=first, second=second), 2: dict(first=first, second=dict(mode='sv39', root=g_root+16384))}, memory)
    request = dict(device=1, address=0x40000000, access='load')
    assert model.translate(request)['pa'] == DATA
    denied = model.translate(dict(request, device=2))
    assert denied['status'] == 'fault' and denied['stage'] == 'second'
    model.memory[leaf] = ((DATA + 4096) >> 12 << 10) | 0xdf
    assert model.translate(request)['pa'] == DATA
    model.enqueue(dict(op='iotinval', device=2))
    model.process_command()
    assert model.translate(request)['pa'] == DATA
    model.enqueue(dict(op='iotinval', device=1))
    model.process_command()
    assert model.translate(request)['pa'] == DATA + 4096


@pytest.mark.parametrize('mode', ['sv39', 'sv48', 'sv57'])
def test_generated_scenarios(tmp_path, mode):
    import json
    from rvw.regress.mmu_iommu import generate, run
    spec = generate(19, mode)
    assert spec == generate(19, mode)
    path = tmp_path / 'description.json'
    path.write_text(json.dumps(spec))
    report = run(path)
    assert report['status'] == 'inconclusive' and not report['c1_bound']
    assert report['steps'][-2]['expected']['pa'] == 0x80201000
    capture = tmp_path / 'capture.json'
    records = [r['expected'] for r in report['steps']]
    capture.write_text(json.dumps(dict(schema='rvw.iommu-observations/1', records=records)))
    assert run(path, capture)['status'] == 'inconclusive'
    records[-2]['pa'] ^= 4096
    capture.write_text(json.dumps(dict(schema='rvw.iommu-observations/1', records=records)))
    assert run(path, capture)['status'] == 'mismatch'


def test_c1_binding(tmp_path):
    import hashlib
    import json
    from rvw.regress.mmu_iommu import generate, run
    path = tmp_path / 'description.json'
    path.write_text(json.dumps(generate()))
    expected = [r['expected'] for r in run(path)['steps']]
    identity = dict(core='fixture', config='fixture', elf_sha256='a'*64, rtl_sha256='b'*64, source={}, seed=1)
    c1 = tmp_path / 'result.json'
    c1.write_text(json.dumps(dict(schema='rvw.run/1', status='pass', **identity,
                                 details=dict(iommu_description_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))))
    capture = tmp_path / 'capture.json'
    raw = dict(schema='rvw.iommu-observations/1', identity=identity,
               c1_sha256=hashlib.sha256(c1.read_bytes()).hexdigest(), records=expected)
    capture.write_text(json.dumps(raw))
    assert run(path, capture, c1)['status'] == 'consistent'
    raw['identity']['seed'] = 2
    capture.write_text(json.dumps(raw))
    assert run(path, capture, c1)['status'] == 'inconclusive'


def test_cli_and_mcp(tmp_path):
    from rvw.cli import build_parser
    from rvw.mcp.registry import Registry
    args = build_parser().parse_args(['regress', 'mmu', 'iommu', '--generate', '--seed', '19'])
    assert args.generate and args.seed == 19
    registry, problems = Registry.discover({'regress'})
    try:
        assert not problems
        assert registry.call('regress_mmu_iommu_generate', {'seed': 19})['seed'] == 19
    finally:
        registry.jobs.shutdown()
