"""Ssnpm guest data masking and the HLVX masking exemption."""


def validate(s):
    option = s['guest_pointer']
    if not isinstance(option, dict) or not {'pmlen', 'privilege'} <= set(option) or set(option) - {'pmlen', 'privilege', 'context'} or type(option['pmlen']) is not int or option['pmlen'] not in (0,7,16) or option['privilege'] not in ('S','U'):
        raise ValueError('guest_pointer requires pmlen 0/7/16 and privilege S/U')
    if option.get('context', 'M') not in ('M','U') or option.get('context') == 'U' and option['privilege'] != 'U':
        raise ValueError('U-mode HUPMM requires VU privilege')
    if s.get('guest_op') not in ('hlv.d','hlvx.wu','hsv.d') or s.get('guest_switch') or s.get('guest_fault') or 'ad_expect' in s or s.get('guest_trap','m') != 'm':
        raise ValueError('guest pointer requires a standalone M-mode hypervisor access')
    expected = 'success' if option['pmlen'] and s['guest_op'] != 'hlvx.wu' else 'page-fault'
    if s['expect'] != expected:
        raise ValueError('guest pointer expectation differs from masking rules')


def assembly(s):
    from .mmu_hypervisor import assembly as guest_assembly
    validate(s)
    option = s['guest_pointer']
    inner = {k:v for k,v in s.items() if k != 'guest_pointer'}
    code = guest_assembly(inner)
    tag = 0x8000000040000000
    csr = 'henvcfg' if option['privilege'] == 'S' else 'senvcfg'
    shift = 32
    if option.get('context') == 'U':
        csr, shift = 'hstatus', 48
    pmm = {0:0, 7:2, 16:3}[option['pmlen']]
    setup = f''' li t0, {3 << shift}
 csrc {csr}, t0
 li t0, {pmm << shift}
 csrs {csr}, t0
 csrr t1, {csr}
 li t2, {3 << shift}
 and t1, t1, t2
 bne t0, t1, fail
'''
    code = code.replace(' li t3, 0x40000000', setup + f' li t3, {tag}')
    code = code.replace(' li t1, 0x40000000', f' li t1, {tag}')
    if option['privilege'] == 'U':
        code = code.replace(' li t0, 256\n csrw hstatus', ' li t0, 0\n csrw hstatus')
    if option.get('context') == 'U':
        code = code.replace('access_site:\n', """ csrw satp, zero
 sfence.vma x0, x0
 li t0, 512
 csrs hstatus, t0
 li t0, 0x1800
 csrc mstatus, t0
 la t0, access_site
 csrw mepc, t0
 mret
access_site:
""", 1)
    return code


def matrix(config):
    if not isinstance(config, dict) or set(config) != {'modes'} or not config['modes'] or set(config['modes']) - {'sv39','sv48','sv57'}:
        raise ValueError('guest_pointer_matrix requires supported modes')
    rows = []
    for mode in config['modes']:
        for privilege in ('S','U'):
            for pmlen in (0,7,16):
                for op in ('hlv.d','hlvx.wu','hsv.d'):
                    rows.append(dict(id=f'{mode}-guest-pointer-{privilege.lower()}-{pmlen}-{op.replace(".","-")}',
                                     mode=mode, guest=True, guest_mode=mode, guest_op=op, guest_pointer=dict(pmlen=pmlen,privilege=privilege),
                                     guest_flags='VRWXUAD', flags='VRWXUAD' if privilege == 'U' else 'VRWXAD', level=0,
                                     access='store' if op == 'hsv.d' else 'load', expect='success' if pmlen and op != 'hlvx.wu' else 'page-fault',
                                     bins=[f'{mode}.guest-pointer.{privilege}.{pmlen}.{op}']))
    for row in list(rows):
        if row['guest_pointer']['privilege'] == 'U':
            rows.append(dict(row, id=row['id']+'-hupmm', guest_pointer=dict(row['guest_pointer'], context='U'), bins=[row['bins'][0]+'.hupmm']))
    return rows
