"""All 64 requested control combinations across disabled feature profiles."""
from .programs import HEAD, TAIL
from .disabled import BITS, enter


def programs(config):
    feature=config['disabled']['feature']
    letters=config.get('isa','rv64im_zicsr_zifencei').split('_')[0][4:]
    if 'g' in letters:letters += 'imafd'
    if feature not in ('fs-off','vs-off','no-float','no-vector','no-supervisor'):
        raise ValueError('unknown disabled feature profile')
    if feature=='fs-off' and 'f' not in letters:raise ValueError('fs-off needs F')
    if feature=='vs-off' and 'v' not in letters:raise ValueError('vs-off needs V')
    if feature=='no-float' and ('f' in letters or 'v' in letters):raise ValueError('no-float needs F and V absent')
    if feature=='no-vector' and 'v' in letters:raise ValueError('no-vector needs V absent')
    absent=feature=='no-supervisor'
    if absent and config.get('priv')!='mu':raise ValueError('no-supervisor needs priv=mu')
    if not absent and config.get('priv','msu')!='msu':raise ValueError('other profiles require priv=msu')
    modes=config.get('modes',['M','U'] if absent else ['M','S','U'])
    if absent and any(m not in ('M','U') for m in modes):raise ValueError('supervisor mode is absent')
    head=HEAD
    if absent:
        head=head.replace(' csrw satp, zero\n','').replace(' csrw medeleg, zero\n','').replace(' csrw mideleg, zero\n','')
    operations=({'satp':'csrr a0, satp','sfence':'sfence.vma','sret':'sret'} if absent else
                {feature:'.word 0xf0000053' if feature in ('fs-off','no-float') else '.word 0x000072d7'})
    mask=sum(1<<b for b in BITS.values())
    rows=[]
    for mode in modes:
        for selected in range(64):
            word=sum(1<<bit for index,bit in enumerate(BITS.values()) if selected&(1<<index))
            for operation,instruction in operations.items():
                ident=f'disabled-all-{feature}-{mode.lower()}-{selected:02x}-{operation}'
                # Capture WARL readback, then account for MRET clearing MPRV
                # when entering a privilege below M. No optional bit is assumed.
                text=head+f''' la t0, handler
 csrw mtvec, t0
 li t0, {mask|0x6600}
 csrc mstatus, t0
 li t0, {word}
 csrs mstatus, t0
 csrr s3, mstatus
 li t0, {mask & ~(0x20000 if mode!='M' else 0)}
 and s3, s3, t0
''' +enter(mode)+f'''access_site:
 {instruction}
 j fail
handler:
 csrr t0, mcause
 li t1, 2
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
 csrr t0, mstatus
 li t1, {mask}
 and t0, t0, t1
 bne t0, s3, fail
 j pass
'''+TAIL
                bins=[f'disabled.{feature}.{mode}.requested-mask.{selected:02x}']
                bins += [f'disabled.{feature}.{mode}.requested.{control}.{int(bool(selected&(1<<i)))}'
                         for i,control in enumerate(BITS)]
                rows.append(dict(id=ident,family='disabled',assembly=text,bins=bins,
                    requested_controls=word,spec='https://docs.riscv.org/reference/isa/v20260120/priv/machine.html'))
    return rows
