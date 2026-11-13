import copy
import json
from pathlib import Path
import pytest
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from test_state import fixture, Model

STATE = dict(mode=False, dpc='0x0', dcsr='0x40000003', step=False)
HALTED = dict(mode=True, dpc='0x80000004', dcsr='0x400000c3', step=False)


class DebugModel(Model):
    def __init__(self, row):
        super().__init__(row)
        self.effect['debug'] = dict(mode=False, dpc=0, dcsr=0x40000003, step=False)
    def debug_event(self, action):
        assert action == 'halt'
        return dict(pc=0x800, regs=[0]*32, disasm='debug halt',
                    debug=dict(mode=True, dpc=0x80000004, dcsr=0x400000c3, step=False))


@pytest.mark.parametrize('field', [None, 'mode', 'dpc', 'dcsr'])
def test_debug_entry_and_mutations(tmp_path, field):
    header, row = fixture()
    header['debug'] = True
    row['debug'] = copy.deepcopy(STATE)
    event = dict(event='debug', action='halt', cycle=2, debug=copy.deepcopy(HALTED))
    if field == 'mode':
        event['debug'][field] = False
    elif field:
        event['debug'][field] = hex(int(event['debug'][field], 16)^1)
    path = tmp_path/'trace'
    path.write_text('\n'.join(json.dumps(x) for x in [header, row, event, dict(event='end', cycle=3, status='pass')]))
    result = check(path, DebugModel(row), Platform.load('boom'))
    assert result['status'] == ('match' if field is None else 'mismatch')
    if field:
        assert f'debug.{field}' in result['mismatch']['differences']


def test_native_halt_preserves_next_instruction_boundary(tmp_path, tmp_path_factory):
    from cosim_build import _build
    from model_fixtures import Spike
    source = tmp_path/'nop.S'
    source.write_text('.section .text\n.globl _start\n_start: nop\n nop\n')
    elf = _build(tmp_path_factory, source)
    model = Spike(Platform.load('boom'), elf)
    try:
        assert model.step()['pc_next'] == 0x80000004
        snapshot = model.debug_event('halt')['debug']
        assert snapshot['mode']
        assert snapshot['dpc'] == 0x80000004
        assert (snapshot['dcsr'] >> 6) & 7 == 3  # halt request, not exception
        assert not snapshot['step']
        with pytest.raises(ValueError, match='already'):
            model.debug_event('halt')
    finally:
        model.close()
