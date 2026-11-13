"""RISC-V speculative gadget templates with an explicit receiver ABI."""
import json
from pathlib import Path
import random

KINDS=('v1','v2','v4','rsb')
BODIES={
'v1': '''# a0 is out of bounds during the attack; bounds load delays resolution.
ld t0, 0(s2)
bgeu a0, t0, sec_safe
add t0, s0, a0
lbu t1, 0(t0)
slli t1, t1, 6
add t1, s1, t1
ld t2, 0(t1)
sec_safe:
''',
'v2': '''# The project trains this indirect site to predict sec_transient.
la t0, sec_safe
jalr ra, t0, 0
j sec_after
sec_transient:
lbu t1, 0(s0)
slli t1, t1, 6
add t1, s1, t1
ld t2, 0(t1)
ret
sec_safe:
ret
sec_after:
''',
'v4': '''# s3 initially holds s0. The delayed store replaces it with public s4.
# The project must delay address resolution without changing the alias.
sd s4, 0(s3)
ld t0, 0(s3)
lbu t1, 0(t0)
slli t1, t1, 6
add t1, s1, t1
ld t2, 0(t1)
''',
'rsb': '''# The project primes the return predictor with sec_transient.
la ra, sec_safe
ret
sec_transient:
lbu t1, 0(s0)
slli t1, t1, 6
add t1, s1, t1
ld t2, 0(t1)
j sec_safe
sec_safe:
'''}


def generate(out, seed=1, threshold=10, declares_speculation=False):
    if type(threshold) is not int or threshold<=0:
        raise ValueError('positive receiver threshold required')
    out=Path(out).resolve(); out.mkdir(parents=True,exist_ok=False)
    order=list(range(256)); random.Random(seed).shuffle(order)
    cases=[]
    for kind in KINDS:
        # Receiver scans all possible byte values in a seeded order. s5 points to
        # 256 cycle measurements; the adapter checks them against the paired control.
        receiver=['li t6, 0']
        for index in order:
            receiver += [f'li t0, {index*64}','add t0, s1, t0','rdcycle t3','ld t2, 0(t0)',
                         'rdcycle t4','sub t4, t4, t3',f'sd t4, {index*8}(s5)',
                         f'li t5, {threshold}','sltu t5, t4, t5','or t6, t6, t5']
        text='.text\n.global sec_test\nsec_test:\n'+BODIES[kind]+'\n'+ '\n'.join(receiver)+'\nebreak\n'
        (out/(kind+'.S')).write_text(text)
        cases.append(dict(kind=kind,assembly=kind+'.S',expected='no_leak_observed',
                          requires_speculation=declares_speculation))
    result=dict(schema='rvw.sec-gadgets/1',status='generated',seed=seed,cases=cases,
                threshold=threshold,declares_speculation=declares_speculation,
                abi={'s0':'secret byte base','s1':'256 cache lines, stride 64',
                     's2':'bounds pointer','s3':'alias pointer slot','s4':'public byte pointer',
                     's5':'256 latency result slots','a0':'v1 attack index'},
                required_hooks=['cold probe lines','predictor training','cycle CSR enabled',
                                'equal architectural reference traces','paired receiver control'])
    (out/'suite.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
