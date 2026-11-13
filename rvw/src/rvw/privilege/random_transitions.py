"""Seeded RV64 trap, delegation and return sequences."""
import random
from .programs import HEAD, TAIL

VERSION = 'privileged-20260120'


def plan(seed, steps, modes):
    rng = random.Random(seed)
    rows = []
    for _ in range(steps):
        mode = rng.choice(modes)
        operation = rng.choice(('illegal', 'breakpoint', 'ecall'))
        cause = {'illegal': 2, 'breakpoint': 3, 'ecall': {'M': 11, 'S': 9, 'U': 8}[mode]}[operation]
        delegated = mode != 'M' and operation != 'ecall' and bool(rng.getrandbits(1))
        rows.append(dict(mode=mode, operation=operation, cause=cause,
                         delegated=delegated, cookie=rng.randrange(1, 1 << 30)))
    return rows


def programs(config):
    if config.get('spec_version') != VERSION:
        raise ValueError('random transitions require privileged-20260120')
    if not config['isa'].startswith('rv64'):
        raise ValueError('random transitions require RV64')
    options = config['random_transitions']
    seeds = options['seeds']; steps = options['steps']; modes = config.get('modes', ['M', 'S', 'U'])
    if not seeds or any(type(s) is not int or s < 0 for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('seeds must be distinct nonnegative integers')
    if type(steps) is not int or not 1 <= steps <= 256:
        raise ValueError('steps must be between 1 and 256')
    rows = []
    for seed in seeds:
        sequence = plan(seed, steps, modes)
        bins = sorted({f"random.{s['mode']}.{s['operation']}.{'S' if s['delegated'] else 'M'}" for s in sequence})
        code = HEAD
        for i, step in enumerate(sequence):
            code += stage(i, step)
        code += f'step_{steps}:\n j pass\n' + TAIL
        rows.append(dict(id=f'random-privilege-{seed}', family='random-privilege', bins=bins,
                         assembly=code, spec_version=VERSION, transition_plan=sequence))
    return rows


def stage(i, step):
    mode = step['mode']; delegated = step['delegated']; cause = step['cause']
    operation = {'illegal': '.word 0', 'breakpoint': 'ebreak', 'ecall': 'ecall'}[step['operation']]
    # Each completed lower-mode probe exits to M through a separate ECALL.
    # ECALL is never delegated. The first trap must return through xRET.
    code = f'''step_{i}:
 la t0, machine_{i}
 csrw mtvec, t0
 la t0, supervisor_{i}
 csrw stvec, t0
 li t0, {(1 << cause) if delegated else 0}
 csrw medeleg, t0
 li s0, {step['cookie']}
 li s3, 0
 li t0, 0x1800
 csrc mstatus, t0
 li t0, {dict(M=3, S=1, U=0)[mode] << 11}
 csrs mstatus, t0
 la t0, probe_{i}
 csrw mepc, t0
 mret
probe_{i}:
 {operation}
resume_{i}:
 li t0, 1
 bne s3, t0, fail
exit_{i}:
 ecall
 j fail
machine_{i}:
 bnez s3, completed_{i}
'''
    code += ' j fail\n' if delegated else check(i, step, 'm')
    code += f'''supervisor_{i}:
'''
    code += check(i, step, 's') if delegated else ' j fail\n'
    code += f'''completed_{i}:
 csrr t0, mcause
 li t1, {dict(M=11, S=9, U=8)[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, exit_{i}
 bne t0, t1, fail
 li t0, {step['cookie']}
 bne s0, t0, fail
 j step_{i+1}
'''
    return code


def check(i, step, level):
    status_mask = 0x1800 if level == 'm' else 0x100
    status_value = (dict(M=3, S=1, U=0)[step['mode']] << 11) if level == 'm' else (0x100 if step['mode'] == 'S' else 0)
    return f''' csrr t0, {level}cause
 li t1, {step['cause']}
 bne t0, t1, fail
 csrr t0, {level}epc
 la t1, probe_{i}
 bne t0, t1, fail
 csrr t0, {level}status
 li t1, {status_mask}
 and t0, t0, t1
 li t1, {status_value}
 bne t0, t1, fail
 li t0, {step['cookie']}
 bne s0, t0, fail
 li s3, 1
 la t0, resume_{i}
 csrw {level}epc, t0
 {level}ret
'''
