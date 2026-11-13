"""Bounded retirement-pair recipes, separate from measured pipeline events."""
from hashlib import sha256
import json
from pathlib import Path
from .sequence import KINDS


def lower(goal, registers, distances=(1, 2, 4), memory=False):
    """Lower a declared sequence goal to setup and an action graph.

    The caller must declare scratch memory support before memory actions are legal.
    Scratch data is program-owned. No device address is inferred.
    """
    if (len(registers) != 3 or len(set(registers)) != 3
            or any(type(r) is not int or not 1 <= r <= 31 for r in registers)):
        raise ValueError('actions need three distinct writable registers')
    if not goal.startswith('sequence:'):
        return {'status':'unsupported', 'reason':'not a retirement sequence goal', 'measured_hits':[]}
    kind, distance = json.loads(goal.split(':', 1)[1])
    if kind not in KINDS or type(distance) is not int or distance not in distances or not 1 <= distance <= 256:
        return {'status':'unsupported', 'reason':'kind or distance outside declared bound', 'measured_hits':[]}
    a,b,base = (f'x{r}' for r in registers)
    preconditions = ['M-mode', 'no interrupts', 'three writable integer registers']
    if 'load' in kind or 'store' in kind:
        if not memory:
            return {'status':'unsupported', 'reason':'project did not declare scratch memory support', 'measured_hits':[]}
        preconditions += ['writable eight-byte program data', 'aligned word access']
    pairs = {'RAW':(f'addi {a}, x0, 1',f'add {b}, {a}, x0'),
             'WAW':(f'addi {a}, x0, 1',f'addi {a}, x0, 2'),
             'WAR':(f'add {a}, {b}, x0',f'addi {b}, x0, 2')}
    if kind in pairs:
        first, second = pairs[kind]
    else:
        after, before = kind.split('-after-')
        def instruction(action, target):
            return {'load':f'lw {a}, 0({base})', 'store':f'sw {a}, 0({base})',
                    'branch':f'beq x0, x0, {target}', 'jump':f'jal x0, {target}'}[action]
        first, second = instruction(before, 'rvw_action_next'), instruction(after, 'rvw_payload_end')
    setup = f'li {a}, 1\nli {b}, 1\n'
    data = ''
    if 'load' in kind or 'store' in kind:
        setup += f'la {base}, rvw_action_scratch\n'
        data = '.pushsection .data\n.balign 8\nrvw_action_scratch: .dword 0\n.popsection\n'
    actions = [first]+['addi x0, x0, 0']*(distance-1)+[second]
    encodings = {f'addi {a}, x0, 1': 0x100013 | registers[0]<<7,
                 f'addi {a}, x0, 2': 0x200013 | registers[0]<<7,
                 f'addi {b}, x0, 2': 0x200013 | registers[1]<<7,
                 f'add {b}, {a}, x0': 0x33 | registers[1]<<7 | registers[0]<<15,
                 f'add {a}, {b}, x0': 0x33 | registers[0]<<7 | registers[1]<<15,
                 f'lw {a}, 0({base})': 0x2003 | registers[0]<<7 | registers[2]<<15,
                 f'sw {a}, 0({base})': 0x2023 | registers[0]<<20 | registers[2]<<15,
                 'addi x0, x0, 0': 0x13}
    words = [0x263 if insn.startswith('beq ') else 0x40006f if insn.startswith('jal ') else encodings[insn]
             for insn in actions]
    source = ('.option norvc\n.option norelax\n'+setup+
              '.global rvw_payload_start, rvw_payload_end\nrvw_payload_start:\n'+
              ''.join(f'.word 0x{word:08x}\n' for word in words)+'rvw_payload_end:\n'+data)
    return {'schema':'rvw.sequence-candidate/1', 'status':'generated', 'goal':goal,
            'kind':kind, 'distance':distance, 'instructions':words, 'preconditions':preconditions,
            'actions':[{'index':i,'assembly':a,'after':i-1 if i else None} for i,a in enumerate(actions)],
            'source_text':source, 'source_sha256':sha256(source.encode()).hexdigest(),
            'measured_hits':[], 'notes':['Retirement pairs are not measured pipeline hazards.']}


def generate(goal, work_dir, registers, distances=(1,2,4), memory=False):
    result = lower(goal, registers, distances, memory)
    if result['status'] == 'generated':
        directory = Path(work_dir); directory.mkdir(parents=True,exist_ok=False)
        (directory/'payload.S').write_text(result.pop('source_text'))
        result['source'] = str(directory/'payload.S')
        (directory/'candidate.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
