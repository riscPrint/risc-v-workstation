"""Reset restart and Smrnmi entry programs with explicit project events."""
from .programs import HEAD, TAIL


def programs(config):
    if config['kind'] == 'reset':
        contract = config['reset']
        count = contract['pulses']
        if type(count) is not int or not 1 <= count <= 16:
            raise ValueError('reset pulses must be in 1..16')
        if not contract.get('state') or not contract.get('invalid_outputs'):
            raise ValueError('reset needs state and output validity contracts')
        rows = []
        for kind in contract.get('kinds', ['warm', 'local']):
            if kind not in ('cold', 'warm', 'local'):
                raise ValueError('reset kind must be cold, warm or local')
            assembly = HEAD + f''' la t0, restart_count
 ld t1, 0(t0)
 li t2, {count}
 beq t1, t2, pass
 bgtu t1, t2, fail
 addi t1, t1, 1
 sd t1, 0(t0)
 fence rw, rw
 la t0, stimulus_step
 sd t1, 0(t0)
reset_wait:
 j reset_wait
''' + TAIL + '''.section .data
.balign 8
.globl restart_count, stimulus_step, stimulus_ack
restart_count: .dword 0
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
            activity = contract.get('activity', {}).get(kind, 'fetch')
            if activity not in ('fetch', 'load', 'store'):
                raise ValueError('reset activity must be fetch, load or store')
            if activity != 'fetch':
                operation = 'ld t3, 0(t0)' if activity == 'load' else 'sd t1, 0(t0)'
                assembly = assembly.replace('reset_wait:\n j reset_wait',
                    f' la t0, probe_data\nreset_wait:\n {operation}\n j reset_wait')
                assembly += 'probe_data: .dword 0\n'
            events = [dict(step=i, kind='reset', reset_kind=kind, preserve_ram=True,
                           **({'schedule': contract['schedule'][kind]} if 'schedule' in contract else {}))
                      for i in range(1, count + 1)]
            rows.append(dict(id='reset-' + kind, assembly=assembly, family='reset',
                bins=['reset.' + kind], events=events, reset_contract=contract,
                reference_unavailable='Spike CLI cannot drive project reset pulses'))
        return rows
    nmi = config['nmi']
    if 'smrnmi' not in config.get('isa', ''):
        raise ValueError('NMI entry program requires Smrnmi')
    cause = nmi['cause']
    if type(cause) is not int or not 0 <= cause < 1 << 63:
        raise ValueError('NMI cause must be an unsigned 63-bit value')
    # The project must place .nmi at its implemented NMI vector.
    assembly = HEAD + ''' la t0, trap
 csrw mtvec, t0
 li t0, 8
 csrs 0x744, t0
 li s0, 0
 li s1, 0x12345
 la t0, stimulus_step
 li t1, 1
 sd t1, 0(t0)
nmi_wait:
 beqz s0, nmi_wait
 li t0, 0x12345
 bne s1, t0, fail
 j pass
trap:
 csrr t0, mcause
 li t1, 11
 bne t0, t1, fail
 csrr t0, mepc
 la t1, nested_ecall
 bne t0, t1, fail
 addi t0, t0, 4
 csrw mepc, t0
 mret
''' + TAIL + f'''.section .nmi,"ax"
.balign 4
.globl nmi_handler
nmi_handler:
 csrr t0, 0x742
 li t1, {(1 << 63) | cause}
 bne t0, t1, fail
 csrr t0, 0x744
 andi t0, t0, 8
 bnez t0, fail
 csrr s2, 0x741
 la t0, nmi_wait
 bne s2, t0, fail
nested_ecall:
 ecall
 csrr t0, 0x741
 bne t0, s2, fail
 li s0, 1
 .word 0x70200073
.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
    a, b = assembly.split('.section .nmi,', 1)
    b = b.replace(', fail', ', nmi_fail')
    b = b.replace('.section .data', 'nmi_fail:\n la t0, fail\n jr t0\n.section .data')
    assembly = a + '.section .nmi,' + b
    vector = nmi['vector']
    if type(vector) is not int or vector < 0 or vector % 4:
        raise ValueError('NMI vector must be nonnegative and instruction aligned')
    return [dict(id='smrnmi-nested-trap', family='nmi', assembly=assembly,
        bins=['nmi.entry', 'nmi.trap-nesting', 'nmi.recovery'],
        link_options=[f'-Wl,--section-start=.nmi={vector:#x}'],
        events=[dict(step=1, kind='nmi', when_pc='nmi_wait', cause=cause)],
        reference_unavailable='Spike CLI has no replayable external RNMI input')]
