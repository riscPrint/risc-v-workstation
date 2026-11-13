"""Declared semantic domains measured from C2, not inferred reference outcomes."""

VALUE_CLASSES = ['zero', 'one', 'all_ones', 'signed_min', 'signed_max', 'other_positive', 'other_negative']
MODES = ['U', 'S', 'M']


def value_class(value, xlen):
    value = int(value, 0) if isinstance(value, str) else value
    if type(value) is not int or not 0 <= value < 1 << xlen:
        raise ValueError('operand value outside XLEN')
    special = {0: 'zero', 1: 'one', (1 << xlen) - 1: 'all_ones',
               1 << (xlen - 1): 'signed_min', (1 << (xlen - 1)) - 1: 'signed_max'}
    return special.get(value, 'other_negative' if value >> (xlen - 1) else 'other_positive')


def groups(manifest, instructions):
    """The manifest pins exception crosses. No exception cross is guessed legal."""
    settings = manifest.get('semantics')
    if settings is None:
        return []
    if settings.get('version') != 1 or set(settings) - {'version', 'exceptions', 'privilege_modes', 'forms', 'crosses'}:
        raise ValueError('unsupported semantic plan')
    modes = settings.get('privilege_modes', MODES)
    if not modes or len(set(modes)) != len(modes) or set(modes) - set(MODES):
        raise ValueError('invalid semantic privilege modes')
    names = {i['name'] for i in instructions}
    exceptions = settings.get('exceptions', {})
    if set(exceptions) - names:
        raise ValueError('exception instruction not in pinned opcode plan')
    from .semantic_forms import groups as form_groups
    result = form_groups(settings, instructions)
    for item in instructions:
        name = item['name']
        for arg in ('rs1', 'rs2'):
            # FP fields cannot use integer RVFI data. The opcode table alone does
            # not identify register banks. Only explicitly integer source files.
            form = settings.get('forms', {}).get(name, {}).get(arg, {})
            integer_form = form.get('bank') == 'integer'
            from .integer_sources import integer_source
            if integer_form or integer_source(item,arg):
                result.append({'name': f'sem_{name}_{arg}', 'fields': [f'{arg}_class'],
                               'when': {'isa_instruction': name}, 'bins': [[v] for v in VALUE_CLASSES]})
        if 'imm12' in item['args']:
            result.append({'name': f'sem_{name}_imm12', 'fields': ['imm12_class'],
                           'when': {'isa_instruction': name},
                           'bins': [[v] for v in ('zero', 'positive', 'negative', 'minimum', 'maximum')]})
        if name in ('csrrw', 'csrrs', 'csrrc', 'csrrwi', 'csrrsi', 'csrrci'):
            access = ['read_write', 'write'] if name in ('csrrw', 'csrrwi') else ['read_write', 'read']
            result.append({'name': f'sem_{name}_access', 'fields': ['csr_access'],
                           'when': {'isa_instruction': name}, 'bins': [[v] for v in access]})
        causes = exceptions.get(name, [])
        if len(set(causes)) != len(causes) or any(type(c) is not int or not 0 <= c < 64 for c in causes):
            raise ValueError('exception causes must be distinct integers in 0..63')
        if causes:
            result.append({'name': f'sem_{name}_exception', 'fields': ['cause'],
                           'when': {'event': 'instruction_exception', 'fault_instruction': name},
                           'bins': [[v] for v in causes]})
    result.append({'name': 'sem_privilege_transition', 'fields': ['from_mode', 'mode'],
                   'when': {'event': 'privilege_transition'},
                   'bins': [[a, b] for a in modes for b in modes if a != b]})
    return result


class Observer:
    def __init__(self):
        self.previous = None
        self.pending = None
        self.fault_cycle = None
        self.ambiguous_fault = False

    def observe(self, row, observations, isa_plan, xlen):
        if 'semantics' not in isa_plan['manifest']:
            return []
        extra = []
        if 'event' in row:
            if row['event'] == 'trap':
                cause = int(row['cause'], 0) if isinstance(row['cause'], str) else row['cause']
                interrupt = row.get('intr', bool(cause >> (xlen - 1)))
                # C2 has no trap instruction ID. Correlate only an adjacent,
                # unique trap=true record at the same cycle. Late evidence stays unknown.
                if (not interrupt and not self.ambiguous_fault and self.pending and 'cycle' in row
                        and row['cycle'] == self.pending.get('cycle')):
                    extra.append({'event': 'instruction_exception', 'cause': cause,
                                  'fault_instruction': self.pending['fault_instruction']})
                self.pending = None
            elif row['event'] not in ('irq',):
                self.pending = None
                self.previous = None
            return extra
        obs = observations[0]
        if obs.get('trap'):
            cycle = row.get('cycle')
            self.ambiguous_fault = cycle is None or cycle == self.fault_cycle
            self.fault_cycle = cycle
        self.pending = obs if obs.get('trap') and 'fault_instruction' in obs else None
        if self.previous and row['order'] == self.previous['order'] + 1:
            before = self.previous['mode']
            if before in MODES and obs['mode'] in MODES and before != obs['mode']:
                extra.append({'event': 'privilege_transition', 'from_mode': before, 'mode': obs['mode']})
        self.previous = obs
        if obs.get('trap'):
            return extra
        for arg in ('rs1', 'rs2'):
            if (f'isa_{arg}' in obs or f'form_{arg}' in obs) and f'{arg}_rdata' in row:
                obs[f'{arg}_class'] = value_class(row[f'{arg}_rdata'], xlen)
        if 'isa_imm12' in obs:
            v = obs['isa_imm12']
            obs['imm12_class'] = {0: 'zero', 2048: 'minimum', 2047: 'maximum'}.get(
                v, 'negative' if v & 2048 else 'positive')
        return extra
