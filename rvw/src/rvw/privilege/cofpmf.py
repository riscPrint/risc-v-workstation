"""Sscofpmf 1.0 CSR, local-interrupt and project event campaigns."""
from dataclasses import dataclass
from .programs import HEAD, TAIL
from .disabled import enter

VERSION = 'Sscofpmf-1.0'
SPEC = 'https://docs.riscv.org/reference/isa/v20260120/priv/sscofpmf.html'
OF = 1 << 63
IRQ = 1 << 13


@dataclass
class Counter:
    """One 64-bit counter; writes never create an overflow request."""
    value: int = 0
    overflow: bool = False
    pending: bool = False
    inhibited: bool = False

    def write(self, value):
        self.value = value & ((1 << 64) - 1)

    def increment(self, amount=1):
        if self.inhibited:
            return
        total = self.value + amount
        self.value = total & ((1 << 64) - 1)
        if total >= 1 << 64 and not self.overflow:
            self.overflow = True
            self.pending = True


def programs(config):
    if config.get('spec_version') != VERSION:
        raise ValueError('sscofpmf requires Sscofpmf-1.0')
    if not config['isa'].startswith('rv64') or not {'sscofpmf', 'zihpm'} <= set(config['isa'].split('_')):
        raise ValueError('sscofpmf campaign requires RV64, Sscofpmf and Zihpm')
    opts = config['cofpmf']
    counter = opts['counter']
    if type(counter) is not int or not 3 <= counter <= 31:
        raise ValueError('counter must be 3..31')
    event = opts.get('event_selector')
    if event is not None and (type(event) is not int or not 0 < event < 1 << 56):
        raise ValueError('event_selector must be a nonzero 56-bit project value')
    if event is not None and opts.get('counter_bits') != 64:
        raise ValueError('hardware event campaign requires counter_bits = 64')
    bound = opts.get('poll_iterations', 512)
    if type(bound) is not int or not 32 <= bound <= 4096:
        raise ValueError('poll_iterations must be 32..4096')
    csr = f'0x{0x320 + counter:x}'
    count_csr = f'0x{0xb00 + counter:x}'
    mask = 1 << counter
    setup = HEAD + f' li t0, {mask}\n csrs mcountinhibit, t0\n csrw {csr}, zero\n li t0, {IRQ}\n csrc mip, t0\n'
    rows = []
    # M-mode always reads OF; lower-mode visibility uses mcounteren.
    for mode in config.get('modes', ['M', 'S', 'U']):
        for enabled in (0, 1):
            code = setup + f' li t0, {OF}\n csrw {csr}, t0\n li t0, {mask if enabled else 0}\n csrw mcounteren, t0\n'
            code += ' la t0, handler\n csrw mtvec, t0\n' + enter(mode)
            code += f'''access_site:
 csrr t1, 0xda0
 li t0, {mask}
 and t1, t1, t0
 li t0, {mask if enabled or mode == 'M' else 0}
 bne t0, t1, fail
exit_site:
 ecall
 j fail
handler:
 csrr t0, mcause
 li t1, {2 if mode == 'U' else {'M': 11, 'S': 9}[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'access_site' if mode == 'U' else 'exit_site'}
 bne t0, t1, fail
 j pass
''' + TAIL
            rows.append(row(f'scountovf-{mode.lower()}-{enabled}', code))
    for mode in ('M', 'S'):
        for local, glob in ((0, 1), (1, 0), (1, 1)):
            rows.append(row(f'delivery-{mode.lower()}-{local}-{glob}',
                            delivery(setup, mode, local, glob)))
    if event is not None:
        for case in ('overflow', 'of-disabled', 'minh'):
            code = setup + f''' li t0, {event | (OF if case == 'of-disabled' else (1 << 62) if case == 'minh' else 0)}
 csrw {csr}, t0
 csrr t1, {csr}
 bne t0, t1, fail
 li t0, -32
 csrw {count_csr}, t0
 li t0, {mask}
 csrc mcountinhibit, t0
 li s0, {bound}
count_window:
 nop
 addi s0, s0, -1
 bnez s0, count_window
 li t0, {mask}
 csrs mcountinhibit, t0
 csrr t1, {count_csr}
'''
            # Event must count this instruction loop. It is project data, never guessed.
            code += (' li t0, -32\n bne t1, t0, fail\n' if case == 'minh' else ' bltz t1, fail\n')
            code += f''' csrr t1, {csr}
 srli t1, t1, 63
 li t0, {0 if case == 'minh' else 1}
 bne t0, t1, fail
 li s0, {bound}
pending_window:
 csrr t1, mip
 li t0, {IRQ}
 and t1, t1, t0
'''
            if case == 'overflow':
                code += ' bnez t1, pass\n addi s0, s0, -1\n bnez s0, pending_window\n j fail\n'
            else:
                code += ' bnez t1, fail\n addi s0, s0, -1\n bnez s0, pending_window\n j pass\n'
            item = row('hardware-' + case, code + TAIL)
            item['reference_unavailable'] = 'Spike has no project HPM event counting; hardware event execution needs a project reference adapter'
            item['hardware_event'] = dict(counter=counter, event_selector=event, poll_iterations=bound,
                                          scope='64-bit counter; project event must count the instruction loop')
            rows.append(item)
    return rows


def row(name, assembly):
    return dict(id='sscofpmf-' + name, family='sscofpmf', bins=['sscofpmf.' + name],
                spec=SPEC, assembly=assembly)


def delivery(setup, mode, local, glob):
    level = mode.lower()
    code = setup + f''' la t0, handler
 csrw {level}tvec, t0
 li s0, 0
 li t0, {IRQ if mode == 'S' else 0}
 csrw mideleg, t0
 li t0, {IRQ if local else 0}
 csrw mie, t0
'''
    if mode == 'S':
        code += enter('S') + 'access_site:\n'
    code += f''' li t0, {2 if mode == 'S' else 8}
 {'csrs' if glob else 'csrc'} {level}status, t0
 li t0, {IRQ}
wait_begin:
 csrs {level}ip, t0
 li s1, 128
wait_loop:
 addi s1, s1, -1
 bnez s1, wait_loop
wait_end:
 li t0, {1 if local and glob else 0}
 bne s0, t0, fail
 csrr t1, {level}ip
 li t0, {IRQ}
 and t1, t1, t0
 li t0, {0 if local and glob else IRQ}
 bne t1, t0, fail
'''
    # S-mode needs an ECALL to return to M before it reports tohost.
    if mode == 'S':
        code += ' la t0, completed\n csrw stvec, t0\n ecall\n j fail\n'
        # ECALL is not delegated, so give mtvec its own completion handler.
        code = code.replace(' li s0, 0\n', ' la t0, completed\n csrw mtvec, t0\n li s0, 0\n', 1)
    else:
        code += ' j pass\n'
    code += f'''handler:
 bnez s0, fail
 csrr t0, {level}cause
 li t1, {(1 << 63) | 13}
 bne t0, t1, fail
 csrr t0, {level}epc
 la t1, wait_begin
 bltu t0, t1, fail
 la t1, wait_end
 bgeu t0, t1, fail
 csrr t0, {level}status
 andi t0, t0, {2 if mode == 'S' else 8}
 bnez t0, fail
 li t0, {IRQ}
 csrc {level}ip, t0
 li s0, 1
 {level}ret
'''
    if mode == 'S':
        code += 'completed:\n csrr t0, mcause\n li t1, 9\n bne t0, t1, fail\n j pass\n'
    return code + TAIL
