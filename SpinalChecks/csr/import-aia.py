#!/usr/bin/env python3
"""Supplement the 26 documented address-table gaps from pinned AIA field layouts.

Positions and alias facts are data. This is not an AIA behavior interpreter.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REVISION='9507866427961d4ec2d2400ea875103b2a09520b'
HIGH = dict(sieh='sie',siph='sip',hidelegh='hideleg',hvienh='hvien',hviph='hvip',
            vsieh='vsie',vsiph='vsip',midelegh='mideleg',mieh='mie',mvienh='mvien',mviph='mvip',miph='mip')


def build(root,gaps):
    root=Path(root)
    revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True,timeout=5).strip()
    if revision!=REVISION: raise ValueError('AIA source revision does not match the import pin')
    paths=['src/CSRs.adoc','src/MSLevel.adoc','src/VSLevel.adoc','src/IMSIC.adoc']
    sources={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
    address_text=(root/'src/CSRs.adoc').read_text().lower()
    rows=gaps.get('missing_field_definitions') or gaps['resolved_field_definitions']
    registers={}
    def field(location,policy,**extra):
        return dict(location=location,type=policy,**extra)
    for row in rows:
        name=row['name']
        if '`'+name+'`' not in address_text or f"0x{row['address']:03x}" not in address_text:
            raise ValueError('address table does not contain '+name)
        definition=dict(name=name,address=row['address'],priv_mode=row['access'][0],
                        writable=row['access'].endswith('RW'),length='XLEN',fields={},
                        definedBy='Smaia' if row['access'][0]=='M' else 'Ssaia')
        fields=definition['fields']
        if name in HIGH:
            definition.update(length=32,requires_alias_model=True)
            for bit in range(32):
                fields['I'+str(bit+32)]=field(bit,'project-defined interrupt bit',alias=f'{HIGH[name]}[{bit+32}]')
        elif name.endswith('topei'):
            fields.update(IID=field('26-16','RO'),IPRIO=field('10-0','RO'))
            definition.update(requires_environment_model=True,write_effect='claim current pending interrupt; written data is ignored')
        elif name.endswith('topi'):
            fields.update(IID=field('27-16','RO'),IPRIO=field('7-0','RO'))
            definition['requires_environment_model']=True
        elif name=='hvictl':
            fields.update(VTI=field(30,'RW'),IID=field('27-16','WARL'),DPR=field(9,'RW'),
                          IPRIOM=field(8,'RW'),IPRIO=field('7-0','RW'))
            definition['requires_environment_model']=True
        elif name.startswith('hviprio'):
            second=name.startswith('hviprio2')
            identities=list(range(16,24)) if second else [0,1,4,5,8,13,14,15]
            high=name.endswith('h')
            definition['length']=32 if high else 64
            for slot,identity in enumerate(identities):
                if not second and slot in (0,2,4): continue
                if high and slot<4: continue
                offset=(slot-4 if high else slot)*8
                info=field(f'{offset+7}-{offset}','WARL or read-only zero')
                if high: info['alias']=name[:-1]+'.P'+str(identity)
                fields['P'+str(identity)]=info
            if high: definition['requires_alias_model']=True
        elif name in ('mvien','mvip','hvien'):
            definition.update(length=64,requires_environment_model=True)
            low=[1,9] if name=='mvien' else [1,5,9] if name=='mvip' else []
            for bit in [*low,*range(13,64)]:
                fields['I'+str(bit)]=field(bit,'project-dependent interrupt bit')
            if name=='mvip':
                for bit in low: fields['I'+str(bit)]['alias']='mip bit under mvien and STCE conditions'
        else: raise ValueError('unmapped gap '+name)
        registers[name]=dict(definition=definition,source='src/CSRs.adoc',sha256=sources['src/CSRs.adoc'],
            field_sources=sources,upstream='https://github.com/riscv/riscv-aia',revision=REVISION,
            notices=['RISC-V International, RISC-V Advanced Interrupt Architecture',
                     'SPDX-License-Identifier: CC-BY-4.0',
                     'Field layouts transcribed; behavioral interpretation is not included.'])
    if len(registers)!=26: raise ValueError('expected the 26 documented gaps')
    return dict(schema='rvw.csr-catalog-supplement/1',upstream='https://github.com/riscv/riscv-aia',
                revision=REVISION,sources=sources,registers=registers,
                limits=['Field positions and alias facts only. Project semantics and environment bindings remain required.'])


if __name__=='__main__':
    gaps=json.loads(Path(sys.argv[2]).read_text())
    result=build(sys.argv[1],gaps)
    Path(sys.argv[3]).write_text(json.dumps(result,indent=2)+'\n')
