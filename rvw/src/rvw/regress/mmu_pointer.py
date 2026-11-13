"""Project-selected M/S/U pointer controls and tagged fetch interactions."""


def validate(s):
    if type(s['pointer_mask']) is not int or s['pointer_mask'] not in (0, 7, 16):
        raise ValueError('pointer_mask must be 0, 7 or 16')
    extension = s.get('pointer_extension', 'smnpm')
    if extension in ('sspm', 'supm'):
        if s.get('pointer_controller') != {'sspm': 'smnpm', 'supm': 'ssnpm'}[extension]:
            raise ValueError('Sspm/Supm require an explicit project pointer controller')
        extension = s['pointer_controller']
    if 'pointer_controller' in s and s.get('pointer_extension', 'smnpm') not in ('sspm', 'supm') and s['pointer_controller'] != extension:
        raise ValueError('pointer controller differs from extension')
    if extension not in ('smnpm', 'ssnpm', 'smmpm'):
        raise ValueError('unsupported pointer extension; select a standard controller for Sspm/Supm')
    if s.get('mode') not in ('sv39', 'sv48', 'sv57') or s['access'] not in ('load', 'fetch') or s['level'] != 0:
        raise ValueError('pointer masking requires an RV64 level-zero load')
    expected_privilege = 'U' if extension == 'ssnpm' else 'S'
    if extension != 'smmpm' and (s.get('privilege', 'S') != expected_privilege or not s.get('mprv', True) or s.get('satp_mode') == 'bare'):
        raise ValueError('pointer extension has the wrong effective privilege')
    if s['access'] == 'fetch' and extension == 'smmpm':
        raise ValueError('M-mode pointer fetch needs a separate harness')
    if extension == 'smmpm' and (s.get('mprv', True) or s.get('satp_mode') != 'bare'):
        raise ValueError('smmpm requires M-mode Bare data access')
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'pointer_mask', 'va', 'pointer_extension', 'pointer_controller', 'privilege', 'mprv', 'satp_mode'}:
        raise ValueError('unsupported pointer-mask scenario option')
    from .mmu import number
    if not 0 <= number(s.get('va', 0x40000000)) < 1 << 47:
        raise ValueError('pointer-mask VA must fit the common positive 48-bit range')
    if s['expect'] != ('page-fault' if s['access'] == 'fetch' else 'success' if s['pointer_mask'] else 'access-fault' if extension == 'smmpm' else 'page-fault'):
        raise ValueError('tagged pointer requires success when masking is enabled, otherwise a page fault')


def setup(s):
    pmm = {0: 0, 7: 2, 16: 3}[s['pointer_mask']]
    csr = {'smnpm': 'menvcfg', 'ssnpm': 'senvcfg', 'smmpm': 'mseccfg'}[s.get('pointer_controller', s.get('pointer_extension', 'smnpm'))]
    return f'''li t0, 0x300000000
 csrc {csr}, t0
 li t0, {pmm << 32}
 csrs {csr}, t0
 csrr t1, {csr}
 li t2, 0x300000000
 and t1, t1, t2
 bne t0, t1, fail
 '''


def matrix(config=None):
    if config is not None:
        if not isinstance(config, dict) or set(config) != {'modes', 'extensions', 'controllers'} or not config['modes'] or set(config['modes']) - {'sv39', 'sv48', 'sv57'} or not config['extensions'] or set(config['extensions']) - {'smnpm', 'ssnpm', 'smmpm', 'sspm', 'supm'}:
            raise ValueError('invalid pointer_matrix selection')
        for extension in set(config['extensions']) & {'sspm', 'supm'}:
            if config['controllers'].get(extension) != {'sspm': 'smnpm', 'supm': 'ssnpm'}[extension]:
                raise ValueError('pointer_matrix requires explicit Sspm/Supm controllers')
    from .mmu import DATA
    cases = []
    for extension in ('ssnpm', 'smmpm'):
        for mode in ('sv39', 'sv48', 'sv57'):
            for pmlen in (0, 7, 16):
                row = dict(id=f'{extension}-{mode}-{pmlen}', mode=mode, level=0, access='load',
                           flags='VRWUAD' if extension == 'ssnpm' else 'VRWAD', pointer_mask=pmlen,
                           pointer_extension=extension, expect='success' if pmlen else 'page-fault' if extension == 'ssnpm' else 'access-fault',
                           bins=[f'{extension}.{mode}.{pmlen}'])
                if extension == 'ssnpm':
                    row['privilege'] = 'U'
                else:
                    row.update(mprv=False, satp_mode='bare', va=DATA)
                cases.append(row)
    for extension, controller in (('sspm', 'smnpm'), ('supm', 'ssnpm')):
        for mode in ('sv39', 'sv48', 'sv57'):
            for pmlen in (0, 7, 16):
                cases.append(dict(id=f'{extension}-{mode}-{pmlen}', mode=mode, level=0, access='load', flags='VRWUAD' if extension == 'supm' else 'VRWAD',
                                  pointer_extension=extension, pointer_controller=controller, pointer_mask=pmlen, privilege='U' if extension == 'supm' else 'S',
                                  expect='success' if pmlen else 'page-fault', bins=[f'{extension}.{mode}.{pmlen}']))
    for extension in ('smnpm', 'ssnpm'):
        for mode in ('sv39', 'sv48', 'sv57'):
            for pmlen in (0, 7, 16):
                cases.append(dict(id=f'{extension}-{mode}-{pmlen}-fetch', mode=mode, level=0, access='fetch', flags='VXUAD' if extension == 'ssnpm' else 'VXAD',
                                  pointer_extension=extension, pointer_mask=pmlen, privilege='U' if extension == 'ssnpm' else 'S',
                                  expect='page-fault', bins=[f'{extension}.{mode}.{pmlen}.fetch']))
    return cases if config is None else [s for s in cases if s['mode'] in config['modes'] and s['pointer_extension'] in config['extensions']]
