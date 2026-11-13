"""Compile literal RV32 MMIO actions to software and a CPU-backed virtual sequence."""
import json
from pathlib import Path

from .scenario import plan


def word(value, name):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError(name + ' must be a literal 32-bit unsigned integer')
    return value


def compile_scenario(data, out, *, baremetal='baremetal', pyuvm='pyuvm', finisher):
    if not baremetal or not pyuvm or baremetal == pyuvm:
        raise ValueError('select two distinct backend names')
    plans = {name: plan(data, name) for name in (baremetal, pyuvm)}
    first, second = plans[baremetal], plans[pyuvm]
    if any(p['unit'] != 'cycles' for p in plans.values()):
        raise ValueError('execution observations use cycles')
    if [a['id'] for a in first['actions']] != [a['id'] for a in second['actions']]:
        raise ValueError('CPU-backed sequence needs the same action order in both plans')
    finisher = word(finisher, 'finisher')
    if finisher % 4:
        raise ValueError('finisher must be word aligned')
    operations = []
    assembly = ['.option norvc', '.section .text', '.global _start', '_start:']
    for index, action in enumerate(first['actions']):
        other = second['actions'][index]
        if action['operation'] not in ('read32', 'write32') or other['operation'] != action['operation']:
            raise ValueError('execution bindings must select read32 or write32')
        if action.get('needs') or action.get('produces'):
            raise ValueError('dynamic data flow needs a project execution binding')
        address = word(action['args']['address'], 'address')
        if address % 4 or address == finisher:
            raise ValueError('actions need aligned addresses distinct from the finisher')
        operation = action['operation']
        expected = action.get('expect', {}).get('value')
        value = word(action['args'].get('value', 0), 'value')
        if operation == 'read32' and expected is None:
            raise ValueError('each read needs an expected value')
        expected = word(value if expected is None else expected, 'expected value')
        if operation == 'write32' and expected != value:
            raise ValueError('write expectation must match its requested payload')
        assembly += [f'  # action {index}', f'  li t1,0x{address:08x}']
        if operation == 'write32':
            assembly += [f'  li t0,0x{value:08x}', '  sw t0,0(t1)']
        else:
            assembly += ['  lw t0,0(t1)', f'  li t2,0x{expected:08x}', '  bne t0,t2,scenario_fail']
        operations.append(dict(id=action['id'], operation=operation, address=address,
                               value=value, expected=expected))
    assembly += ['  li t0,1', '  j scenario_finish', 'scenario_fail:', '  li t0,3',
                 'scenario_finish:', f'  li t1,0x{finisher:08x}', '  sw t0,0(t1)', '1: j 1b']
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'program.S').write_text('\n'.join(assembly) + '\n')
    (out / 'operations.json').write_text(json.dumps(operations, indent=2) + '\n')
    for backend, value in plans.items():
        # Backend names are data. They must not become file paths.
        path = 'baremetal-plan.json' if backend == baremetal else 'pyuvm-plan.json'
        (out / path).write_text(json.dumps(value, indent=2) + '\n')
    (out / 'scenario_sequence.py').write_text(SEQUENCE)
    result = dict(schema='rvw.scenario-compiled/1', status='generated', actions=len(operations),
                  finisher=finisher, scope='serial RV32 MMIO image and CPU-backed pyuvm observation sequence; not executed')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


SEQUENCE = '''"""Generated CPU-backed virtual sequence. The project port starts the CPU image.
The sequence observes each real MMIO transfer. It is not an independent master.
"""
import json
from pathlib import Path
import pyuvm

class ScenarioSequence(pyuvm.uvm_sequence):
    async def body(self):
        here = Path(__file__).resolve().parent
        planned = json.loads((here / 'pyuvm-plan.json').read_text())
        operations = json.loads((here / 'operations.json').read_text())
        self.records = []
        await self.port.start()
        for action in operations:
            actual = await self.port.observe(action)
            assert actual['value'] == action['expected'], action['id'] + ': observed value mismatch'
            self.records.append(dict(id=action['id'], operation=action['operation'],
                start=actual['start'], end=actual['end'], outputs={'value':actual['value']}, data={}, inputs={}))
        await self.port.finish()
        self.observation = dict(schema='rvw.scenario-observation/1', plan_id=planned['plan_id'],
            backend=planned['backend'], unit=planned['unit'], actions=self.records)
        (here / 'pyuvm-observations.json').write_text(json.dumps(self.observation, indent=2) + '\\n')
'''
