import pytest
from rvw.cosim.hypervisor_cases import cases
from rvw.cosim.platform import Platform


@pytest.mark.parametrize('case', cases(), ids=lambda c: c['name'])
def test_native_guest_delegation(tmp_path, tmp_path_factory, case):
    from cosim_build import _build
    from model_fixtures import Spike
    source = tmp_path/'guest.S'
    source.write_text(case['source'])
    elf = _build(tmp_path_factory, source, march='rv64imah_zicsr')
    platform = Platform.load('boom')
    platform.isa = platform.reference_isa = 'rv64imah_zicsr'
    model = Spike(platform, elf)
    seen = []
    try:
        for _ in range(80):
            effect = model.step()
            if effect['insn'] == 0x73:
                assert effect['trap'] and not effect['intr']
                assert effect['hypervisor']['virtual']
                seen.append(dict(mode=effect['mode'], cause=effect['cause'],
                    mode_after=effect['hypervisor']['mode_after'],
                    virtual_after=effect['hypervisor']['virtual_after']))
                if len(seen) == len(case['expected']):
                    break
        assert seen == case['expected']
    finally:
        model.close()
