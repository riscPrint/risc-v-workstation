"""Register maps for the bounded SpinalSoc peripheral profiles."""
from .model import ident


def register(name, offset, access='rw', reset=0):
    return dict(name=name, offset=offset, width=32, access=access, reset=reset,
                read_action='none', write_action='normal')


def peripheral(kind, name, base):
    ident(name)
    if type(base) is not int or base < 0:
        raise ValueError('base must be nonnegative')
    if kind == 'clint':
        size, cls = 0x10000, 'Clint'
        regs = [register('msip',0), register('mtimecmp_low',0x4000,reset=0xffffffff),
                register('mtimecmp_high',0x4004,reset=0xffffffff),
                register('mtime_low',0xbff8,reset=None), register('mtime_high',0xbffc,reset=None)]
    elif kind == 'plic':
        size, cls = 0x400000, 'Plic'
        regs = [register(f'priority_{i}',i*4) for i in range(1,8)]
        regs += [register('pending',0x1000,'r'), register('enable',0x2000), register('threshold',0x200000), register('claim_complete',0x200004,reset=None)]
    elif kind == 'gpio':
        size, cls = 0x100, 'Gpio'
        regs = [register('input',0,'r',None), register('output',4), register('output_enable',8), register('irq_enable',12)]
    elif kind == 'timer':
        size, cls = 0x100, 'Timer'
        regs = [register('control',0), register('count',4,reset=None), register('compare',8,reset=0xffffffff)]
    elif kind == 'watchdog':
        size, cls = 0x100, 'Watchdog'
        status = register('status',16,reset=None)
        status['write_action'] = 'one_to_clear'
        regs = [register('control',0), register('reload',4,reset=0xffffffff),
                register('count',8,'r',None), register('service',12,'w',None), status]
    elif kind == 'finisher':
        size, cls = 0x100, 'Finisher'
        regs = [register('tohost',0)]
    elif kind == 'uart16550':
        size, cls = 0x100, 'Uart16550'
        regs = [register('data_divisor_low',0,reset=None), register('ier_divisor_high',4),
                register('iir_fcr',8,reset=None), register('lcr',12,reset=3),
                register('lsr',20,'r',None), register('scratch',28)]
    elif kind == 'spi':
        size, cls = 0x100, 'Spi'
        regs = [register('data',0,reset=None), register('status',4,reset=None),
                register('config',8,reset=None)]
        regs += [register(n,o,'w',None) for n,o in [('divider',12),('ss_setup',16),('ss_hold',20),('ss_disable',24),('sample_pos',28)]]
    elif kind == 'i2c':
        size, cls = 0x100, 'I2c'
        regs = [register(n,o,reset=None) for n,o in [('tx_data',0),('tx_ack',4),('rx_data',8),('rx_ack',12),('interrupt',32),('master_status',64),('slave_status',68),('slave_override',72)]]
        regs += [register(n,o,'w',None) for n,o in [('interrupt_clear',36),('sampling_divider',40),('timeout',44),('tsu_data',48),('t_low',80),('t_high',84),('t_buf',88)]]
    else:
        raise ValueError('unknown peripheral profile')
    if base % size or base + size > 1 << 32:
        raise ValueError('base must align the device window within 32 bits')
    return dict(region=dict(name=name, kind='mmio', base=base, size=size, permissions='rw', cacheable=False, registers=regs),
                binder=dict(type='project', **{'class':'rvwsoc.'+cls}))
