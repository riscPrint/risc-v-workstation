"""Declarative MMU cross groups and capture-only coverage observations."""


def groups():
    return dict(replace_defaults=True, groups=[
        dict(name='vm_mode_access_result', fields=['vm_mode', 'access', 'result'], when=dict(event='mmu_walk'),
             domains=[['sv32', 'sv39', 'sv48', 'sv57'], ['load', 'store', 'fetch'], ['success', 'page-fault', 'access-fault']]),
        dict(name='vm_nested_stage', fields=['stage', 'vm_mode', 'access', 'result'], when=dict(event='mmu_walk')),
        dict(name='vm_level_fault', fields=['vm_mode', 'level', 'fault'], when=dict(event='mmu_pte')),
        dict(name='vm_pte_permissions', fields=['R', 'W', 'X', 'U', 'A', 'D'], when=dict(event='mmu_pte'), domains=[[False, True]] * 6),
        dict(name='vm_protocol_hart', fields=['kind', 'hart'], when=dict(event='mmu_protocol')),
        dict(name='vm_tlb_protocol', fields=['kind'], when=dict(event='mmu_protocol'),
             domains=[['tlb_fill', 'tlb_hit', 'tlb_invalidate', 'ad_atomic', 'shootdown_request', 'shootdown_ack', 'shootdown_complete', 'memory_type']]),
        dict(name='iommu_context_result', fields=['device', 'process', 'result'], when=dict(event='iommu')),
        dict(name='iommu_stage_access', fields=['stage', 'access', 'result'], when=dict(event='iommu')),
        dict(name='iommu_queue', fields=['queue', 'operation'], when=dict(event='iommu')),
        dict(name='vm_two_stage', fields=['vs_mode', 'g_mode', 'access'], when=dict(event='mmu_two_stage'), domains=[[8,9,10], [8,9,10], ['load','store','fetch']]),
        dict(name='vm_pointer_control', fields=['controller', 'pmm', 'mode'], when=dict(event='mmu_pointer'), domains=[['menvcfg', 'senvcfg', 'mseccfg', 'henvcfg'], [0, 2, 3], ['M', 'S', 'U']]),
        dict(name='vm_control_csr', fields=['csr', 'mode'], when=dict(**{'class': 'csr'})),
        dict(name='vm_trap_cause', fields=['cause'], when=dict(event='trap', interrupt=False), domains=[[1, 5, 7, 12, 13, 15, 20, 21, 22, 23]]),
    ])


def observations(row):
    from .mmu import number, FLAGS
    from .mmu_walk import validate_capture
    result = []
    walks = list(row.get('mmu_walks', []))
    for record in row.get('mmu_nested_walks', []):
        nested = record.get('result') or {}
        if nested.get('vs_walk'):
            walks.append(dict(nested['vs_walk'], kind='mmu_walk', access_id=record['access_id'], mode=record['vs_mode'], root=record['vs_root'], va=record['va'], access=record['access'], stage='vs'))
        for guest in nested.get('g_walks', []):
            walks.append(dict(guest, kind='mmu_walk', access_id=record['access_id'], mode=record['g_mode'], root=record['g_root'], va=guest['gpa'], stage='g'))
    for walk in walks:
        validate_capture(walk)
        common = dict(vm_mode=walk['mode'], access=walk['access'], result=walk['status'], stage=walk.get('stage', 'single'))
        result.append(dict(common, event='mmu_walk'))
        for read in walk['reads']:
            item = dict(common, event='mmu_pte', level=read['level'], fault=read['fault'])
            if not read['fault']:
                item.update({f: bool(number(read['data']) & bit) for f, bit in FLAGS.items()})
            result.append(item)
    for event in row.get('mmu_protocol', []):
        result.append(dict(event, event='mmu_protocol'))
    for event in row.get('iommu', []):
        result.append(dict(event, event='iommu'))
    hypervisor = row.get('hypervisor', {})
    for translation in hypervisor.get('translations', []):
        csrs = hypervisor.get('csrs', {})
        result.append(dict(event='mmu_two_stage', access=translation['access'],
                           vs_mode=number(csrs['0x280']) >> 60, g_mode=number(csrs['0x680']) >> 60))
    for address, controller in [('0x30a', 'menvcfg'), ('0x10a', 'senvcfg'), ('0x747', 'mseccfg'), ('0x60a', 'henvcfg')]:
        if address in row.get('csr_state', {}):
            result.append(dict(event='mmu_pointer', controller=controller, pmm=number(row['csr_state'][address]) >> 32 & 3,
                               mode={0:'U', 1:'S', 3:'M'}.get(row.get('mode'), 'unknown')))
    return result
