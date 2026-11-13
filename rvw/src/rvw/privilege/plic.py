"""PLIC MMIO programs derived from the independent level-gateway model."""
from rvw.cosim.devices import Plic, PlicMap
from .programs import HEAD, TAIL


def programs(config):
    layout = PlicMap(**config['plic'])
    if layout.sources < 2 or layout.contexts < 2 or layout.max_priority < 3:
        raise ValueError('PLIC matrix needs two sources, two contexts and priority 3')
    m = layout
    scenarios = {
        'tie': [('priority', 1, 3), ('priority', 2, 3), ('enable', 0, 6),
                ('level', 2, 1), ('level', 1, 1), ('claim', 0), ('claim', 0)],
        'priority': [('priority', 1, 1), ('priority', 2, 3), ('enable', 0, 6),
                     ('level', 1, 1), ('level', 2, 1), ('claim', 0), ('claim', 0)],
        'threshold-claim': [('priority', 1, 3), ('enable', 0, 2), ('threshold', 0, 3),
                            ('level', 1, 1), ('claim', 0)],
        'contexts': [('priority', 1, 3), ('enable', 0, 2), ('enable', 1, 2),
                     ('level', 1, 1), ('claim', 1), ('claim', 0)],
        'gateway': [('priority', 1, 3), ('enable', 0, 2), ('level', 1, 1),
                    ('claim', 0), ('complete', 0, 1), ('claim', 0),
                    ('level', 1, 0), ('complete', 0, 1), ('claim', 0)],
        'disabled': [('priority', 1, 3), ('enable', 0, 0), ('level', 1, 1),
                     ('claim', 0), ('enable', 0, 2), ('claim', 0)],
    }
    rows = []
    for name, ops in scenarios.items():
        model = Plic(m)
        assembly, events, expected = HEAD, [], []
        # Explicitly clear both sources and both contexts before this scenario.
        setup = [('priority', 1, 0), ('priority', 2, 0), ('enable', 0, 0),
                 ('enable', 1, 0), ('threshold', 0, 0), ('threshold', 1, 0)]
        for index, op in enumerate(setup + ops, 1):
            kind, target, *values = op
            if kind == 'level':
                model.set_level(target, bool(values[0]))
                events.append(dict(step=index, kind='plic-level', source=target, level=bool(values[0])))
                assembly += f''' la t0, stimulus_step
 li t1, {index}
 sd t1, 0(t0)
 la t0, stimulus_ack
1: ld t1, 0(t0)
 li t2, {index}
 bne t1, t2, 1b
'''
                continue
            address = {'priority': m.priority + target * 4,
                       'enable': m.enable + target * m.enable_stride,
                       'threshold': m.context + target * m.context_stride,
                       'claim': m.context + target * m.context_stride + 4,
                       'complete': m.context + target * m.context_stride + 4}[kind]
            assembly += f' li t0, {address}\n'
            if kind == 'claim':
                value = model.read(address)
                expected.append(value)
                assembly += f' lw t1, 0(t0)\n li t2, {value}\n bne t1, t2, fail\n'
            else:
                model.write(address, values[0])
                assembly += f' li t1, {values[0]}\n sw t1, 0(t0)\n fence iorw, iorw\n'
        assembly += ' j pass\n' + TAIL + '''.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
        rows.append(dict(id='plic-' + name, family='plic', bins=['plic.' + name],
            assembly=assembly, events=events, expected_claims=expected,
            reference_unavailable='Spike CLI has no mailbox-driven PLIC source injection'))
    return rows
