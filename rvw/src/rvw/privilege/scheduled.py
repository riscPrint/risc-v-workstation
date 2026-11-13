"""Input-scheduled WFI. The adapter, not Spike, drives the input pins."""
from .programs import head, tail, interrupt_cause


def programs(config):
    wake = config['wake']
    on, off = wake['assert_cycle'], wake['clear_cycle']
    if not (type(on) is int and type(off) is int and 1 < on < off < 30000):
        raise ValueError('wake cycles must satisfy 1 < assert < clear < 30000')
    rows = []
    for cause in wake.get('causes', [3, 7, 11]):
        if cause not in (3, 7, 11):
            raise ValueError('wake causes must be 3, 7 or 11')
        for enabled in (0, 1):
            assembly = head(config) + f''' la t0, handler
 csrw mtvec, t0
 li s0, 0x12345
 li t0, {1 << cause}
 csrw mie, t0
wake_start:
 {'csrsi' if enabled else 'csrci'} mstatus, 8
 wfi
wait_pending:
 csrr t0, mip
 li t1, {1 << cause}
 and t0, t0, t1
 beqz t0, wait_pending
 {'j wait_pending' if enabled else 'j check_state'}
wake_end:
 j fail
handler:
 csrr t0, mcause
 li t1, {interrupt_cause(config, cause)}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, wake_start
 bltu t0, t1, fail
 la t1, wake_end
 bgeu t0, t1, fail
 {'j check_state' if enabled else 'j fail'}
check_state:
 li t0, 0x12345
 bne s0, t0, fail
 csrw mie, zero
 csrci mstatus, 8
 j pass
''' + tail(config)
            rows.append(dict(id=f'scheduled-wfi-{cause}-{enabled}', family='wfi',
                bins=[f'wfi.scheduled.{cause}.{enabled}'], assembly=assembly,
                options={'irq_schedule': f'1:0x0,{on}:0x{1 << cause:x},{off}:0x0'},
                clock_state=wake.get('clock_state', {}),
                reference_unavailable='external input schedule needs a project reference adapter'))
    return rows


def clock_check(samples, required_state):
    """Check sampled stop, stable state, pending event and resumed retirement.

    The adapter samples one observation per reference-clock edge, including
    edges while the core clock is stopped. Caller supplies state masks.
    """
    if not samples or not required_state:
        return {'status': 'inconclusive', 'reason': 'missing clock samples or state masks'}
    if any(a['tick'] >= b['tick'] for a, b in zip(samples, samples[1:])):
        raise ValueError('reference ticks must increase')
    stopped = [i for i, s in enumerate(samples) if s.get('clock_running') is False]
    if not stopped or stopped[0] == 0 or stopped[-1] == len(samples) - 1:
        return {'status': 'inconclusive', 'reason': 'need running, stopped and resumed samples'}
    if stopped != list(range(stopped[0], stopped[-1] + 1)):
        raise ValueError('check each clock pause separately')
    base = samples[stopped[0] - 1]
    unknown = base.get('clock_running') is not True
    for sample in samples[stopped[0]:stopped[-1] + 1]:
        for name, mask in required_state.items():
            if type(mask) is not int or mask <= 0:
                raise ValueError('state masks must be positive integers')
            old, new = base.get('state', {}).get(name), sample.get('state', {}).get(name)
            if old is None or new is None:
                unknown = True
            elif (old ^ new) & mask:
                return {'status': 'fail', 'reason': f'state changed during stop: {name}'}
        if sample.get('retired') is None or base.get('retired') is None:
            unknown = True
        elif sample['retired'] != base['retired']:
            return {'status': 'fail', 'reason': 'retirement during stopped clock'}
    pause = samples[stopped[0]:stopped[-1] + 1]
    resumed = samples[stopped[-1] + 1:]
    if not any(s.get('pending') is True for s in pause):
        unknown = True
    if not any(s.get('clock_running') is True and s.get('retired') is not None
               and base.get('retired') is not None and s['retired'] > base['retired'] for s in resumed):
        unknown = True
    return {'status': 'inconclusive' if unknown else 'pass',
            'reason': 'missing pending or resume observation' if unknown else 'sampled clock pause checked'}
