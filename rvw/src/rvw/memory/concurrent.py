"""Seeded RV64 shared-memory program fragments for project adapters."""
import random


def generate(seed=1, harts=2, length=16):
    if not 2 <= harts <= 16 or not 1 <= length <= 1024:
        raise ValueError('harts must be 2..16 and length 1..1024')
    rng = random.Random(seed)
    programs = []
    for hart in range(harts):
        lines = ['.option norvc', '.text', '.globl _start', '_start:',
                 '  li s0, RVW_SHARED_BASE', '  li s1, 1']
        for step in range(length):
            offset = 8*rng.randrange(1, 5)
            kind = rng.choice(('load', 'store', 'amo', 'lock', 'fence'))
            if kind == 'load':
                lines += [f'  ld t0, {offset}(s0)', '  addi t1, t0, 1']
            elif kind == 'store':
                lines += [f'  li t1, {rng.randrange(1, 65536)}', f'  sd t1, {offset}(s0)']
            elif kind == 'amo':
                suffix = rng.choice(('', '.aq', '.rl', '.aqrl'))
                lines += [f'  addi t2, s0, {offset}', f'  amoadd.d{suffix} t0, s1, (t2)']
            elif kind == 'lock':
                label = f'.Llock_{hart}_{step}'
                lines += [f'{label}:', '  lr.d.aq t0, (s0)', f'  bnez t0, {label}',
                          '  sc.d t1, s1, (s0)', f'  bnez t1, {label}',
                          f'  ld t0, {offset}(s0)', '  addi t0, t0, 1', f'  sd t0, {offset}(s0)',
                          '  fence rw, w', '  sd zero, 0(s0)']
            else:
                lines += ['  fence rw, rw']
        lines += [f'.globl rvw_done_hart{hart}', f'rvw_done_hart{hart}:', f'  j rvw_done_hart{hart}']
        programs.append({'hart': hart, 'assembly': '\n'.join(lines) + '\n',
                         'completion_symbol': f'rvw_done_hart{hart}'})
    return {'schema': 'rvw.concurrent-programs/1', 'seed': seed, 'isa': 'rv64ima',
            'shared_bytes': 40, 'initial_bytes': '00'*40, 'programs': programs,
            'requirements': ['define RVW_SHARED_BASE at aligned writable shared RAM',
                             'link each hart at a separate executable address',
                             'report completion on reaching its completion symbol',
                             'capture complete dependencies for memory axiomatic'],
            'status': 'generated', 'executed': False}
