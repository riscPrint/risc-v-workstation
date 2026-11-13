"""Timer event programs without time-counter reads or counter synchronization."""
from .programs import HEAD,TAIL
MAX=(1<<64)-1
THRESHOLD=1<<39
DELTA=1<<40


def write64(csr,value,xlen):
    if xlen==64:return f' li t0, {value}\n csrw {csr:#x}, t0\n'
    return f' li t0, -1\n csrw {csr:#x}, t0\n li t0, {value>>32}\n csrw {csr+16:#x}, t0\n li t0, {value&0xffffffff}\n csrw {csr:#x}, t0\n'


def delta(value,xlen):
    if xlen==64:
        return f' li t0, {value}\n csrw 0x605, t0\n csrr t1, 0x605\n bne t0, t1, fail\n'
    return f' li t0, {(value>>32)&0xffffffff}\n csrw 0x615, t0\n csrr t1, 0x615\n bne t0, t1, fail\n li t0, {value&0xffffffff}\n csrw 0x605, t0\n csrr t1, 0x605\n bne t0, t1, fail\n'


def wait(ip,bit,wanted,label):
    return f'''.globl timer_{label}
timer_{label}:
 li s0, 1000
1: csrr t0, {ip:#x}
 andi t0, t0, {bit}
 {'bnez' if wanted else 'beqz'} t0, 2f
 addi s0, s0, -1
 bnez s0, 1b
 j fail
2:
'''


def program(xlen,virtual=False):
    if xlen not in (32,64):raise ValueError('timer XLEN must be 32 or 64')
    high=0x31a if xlen==32 else 0x30a
    code=HEAD+f' li t0, {1<<(xlen-1)}\n csrs {high:#x}, t0\n li t0, 2\n csrw mcounteren, t0\n'
    if virtual:
        hcfg=0x61a if xlen==32 else 0x60a
        code+=f' li t0, {1<<(xlen-1)}\n csrs {hcfg:#x}, t0\n li t0, 2\n csrw hcounteren, t0\n'
        code+=delta(0,xlen)+write64(0x24d,THRESHOLD,xlen)+wait(0x644,64,False,'baseline')
        code+=delta(DELTA,xlen)+wait(0x644,64,True,'offset')
        code+=delta(0,xlen)+wait(0x644,64,False,'restored')
        code+=delta(-DELTA,xlen)+wait(0x644,64,True,'negative')
        code+=delta(0,xlen)+wait(0x644,64,False,'final')+write64(0x24d,MAX,xlen)
    else:
        code+=write64(0x14d,0,xlen)+wait(0x344,32,True,'armed')
        code+=write64(0x14d,MAX,xlen)+wait(0x344,32,False,'cleared')
    tail=TAIL if xlen==64 else TAIL.replace(' sd t1, 0(t0)',' sw t1, 0(t0)\n sw zero, 4(t0)')
    return code+' j pass\n'+tail


def contract(config,virtual=False):
    phases=({'baseline':dict(compare=THRESHOLD,delta=0),
             'offset':dict(compare=THRESHOLD,delta=DELTA),
             'restored':dict(compare=THRESHOLD,delta=0),
             'negative':dict(compare=THRESHOLD,delta=-DELTA),
             'final':dict(compare=THRESHOLD,delta=0)} if virtual else
            {'armed':dict(compare=0,delta=0),'cleared':dict(compare=MAX,delta=0)})
    phases={name:{key:hex(value) for key,value in values.items()} for name,values in phases.items()}
    result=dict(source='vstip' if virtual else 'stip',phases=phases,order=list(phases),
                labels={name:'timer_'+name for name in phases})
    if virtual:result['max_reference_time']=hex(THRESHOLD-1)
    if 'max_latency_ticks' in config.get('sstc',{}):
        result['latency_ticks']=config['sstc']['max_latency_ticks']
    return result
