import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3] / 'RiscvSim/tests/ordering'
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('ordering_fixture', ROOT / 'fixture.py')
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
sys.path.remove(str(ROOT))


def test_strict_translation():
    text = '''RISCV SB
{0:x5=1;0:x6=x;1:x6=y;}
 P0 | P1 ;
 sw x5,0(x6) | lw x7,0(x6) ;
 fence rw,rw | fence rw,rw ;
exists (1:x7=1)
'''
    programs = fixture.translate(text)
    assert programs == [[0x00100293, 0x00000313, 0x00532023, 0x0330000f],
                        [0x00400313, 0x00000013, 0x00032383, 0x0330000f]]


@pytest.mark.parametrize('asm', ['amoadd.w x1,x2,(x3)', 'lw x32,0(x1)', 'fence r,w', 'sw x1,4(x2)'])
def test_unsupported_instruction_refused(asm):
    with pytest.raises(ValueError):
        fixture.instruction(asm)


def test_checker_rejects_forbidden_and_incomplete_samples():
    reference = {'cases': [{'test': 'SB', 'allowed': [{'0:x7': 0, '1:x7': 1}]}]}
    samples = [{'test': 'SB', 'harts': 2, 'complete': True,
                'observations': [{'state': {'0:x7': 0, '1:x7': 0}, 'count': 1}]}]
    assert fixture.check(reference, samples)[0]['status'] == 'mismatch'
    samples[0]['complete'] = False
    assert fixture.check(reference, samples)[0]['status'] == 'inconclusive'
    with pytest.raises(ValueError):
        fixture.check(reference, samples * 2)
    with pytest.raises(ValueError):
        fixture.check(reference, [])
