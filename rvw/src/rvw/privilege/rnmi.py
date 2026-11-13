"""Smrnmi 1.0 frame semantics and project-driven entry programs."""
from dataclasses import dataclass
from .programs import HEAD,TAIL
from .disabled import enter

VERSION='Smrnmi-1.0'
SPEC='https://docs.riscv.org/reference/isa/v20260120/priv/smrnmi.html'


@dataclass
class State:
    mode:str='M'
    pc:object=0
    nmie:bool=False
    mprv:bool=False
    frame:dict|None=None

    def write_nmie(self,value):
        if value:self.nmie=True

    def entry(self,cause,vector):
        if not self.nmie:return False
        self.frame=dict(pc=self.pc,mode=self.mode,cause=(1<<63)|cause)
        self.nmie=False;self.mode='M';self.pc=vector
        return True

    @property
    def effective_mprv(self):return self.mode=='M' and self.mprv and self.nmie

    def normal_exception(self,vector):
        self.pc=vector # Ordinary trap CSRs are separate from the RNMI frame.

    def ret(self):
        if self.frame is None:raise ValueError('no saved RNMI frame')
        self.mode=self.frame['mode'];self.pc=self.frame['pc'];self.nmie=True
        if self.mode!='M':self.mprv=False


def head(config):
    hyper='h' in config['isa'].split('_')[0][4:]
    return HEAD+(' li t0, 1\n slli t0, t0, 39\n csrc mstatus, t0\n' if hyper else '')


def programs(config):
    if config.get('spec_version')!=VERSION:raise ValueError('unsupported Smrnmi version')
    if not config['isa'].startswith('rv64') or 'smrnmi' not in config['isa']:
        raise ValueError('RNMI profile requires RV64 Smrnmi')
    if 'smdbltrp' in config['isa']:
        raise ValueError('this RNMI profile uses the no-Smdbltrp exception rules')
    if config['kind']=='nmi-return':return return_programs(config)
    nmi=config['nmi'];vector=nmi['vector'];cause=nmi['cause'];rows=[]
    if vector<0 or vector%4 or not 0<=cause<1<<63:raise ValueError('invalid RNMI vector or cause')
    if nmi.get('pmp_granularity_bytes',4) not in (4,8,16):
        raise ValueError('RNMI MPRV probe needs PMP grain at most 16 bytes')
    if nmi.get('pmp_entries',0)<8:raise ValueError('RNMI MPRV probe requires eight declared PMP entries')
    exception_vector=nmi.get('exception_vector')
    if exception_vector is None and nmi.get('exception_uses_mtvec') is not True:
        raise ValueError('declare the RNMI exception vector or exception_uses_mtvec')
    if exception_vector is not None and (exception_vector<0 or exception_vector%4 or exception_vector==vector):
        raise ValueError('RNMI exception vector must be aligned and distinct')
    ordinary=nmi.get('ordinary_msip')
    if ordinary is not None and (ordinary<0 or ordinary%4):raise ValueError('invalid ordinary MSIP address')
    for mode in ('M','S','U'):
        for nested in (False,True):
            for pending in ((False,True) if ordinary is not None else (False,)):
                code=head(config)+''' la t0, normal_handler
 csrw mtvec, t0
 li s0, 0
 li s1, 0x12345
 li s3, 0
 li s4, 0
 li s6, 0
 li t0, 8
 csrs 0x744, t0
'''+enter(mode)+'''access_site:
 la t0, stimulus_step
 li t1, 1
 sd t1, 0(t0)
rnmi_wait:
 beqz s0, rnmi_wait
'''
                if pending:code+=' beqz s3, rnmi_wait\n'
                code+=f'''main_end:
 li t0, 0x12345
 bne s1, t0, fail
 li t0, {int(nested)}
 bne s6, t0, fail
finish_ecall:
 ecall
 j fail
normal_handler:
 csrr t0, mcause
 li t1, {(1<<63)|3}
 beq t0, t1, ordinary_handler
 li t1, 11
 beq t0, t1, nested_or_finish
 li t1, {dict(M=11,S=9,U=8)[mode]}
 bne t0, t1, fail
 j finish_check
nested_or_finish:
 beqz s4, finish_check
'''
                if nested:
                    code+=' csrr t0, mepc\n la t1, nested_ecall\n bne t0, t1, fail\n addi t0, t0, 4\n csrw mepc, t0\n addi s6, s6, 1\n mret\n'
                else:code+=' j fail\n'
                code+=f'''finish_check:
 csrr t0, mcause
 li t1, {dict(M=11,S=9,U=8)[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, finish_ecall
 bne t0, t1, fail
 csrr t0, 0x744
 andi t0, t0, 8
 beqz t0, fail
 j pass
ordinary_handler:
'''
                if pending:
                    code+=f''' bnez s4, fail
 csrr t0, mepc
 la t1, rnmi_wait
 bltu t0, t1, fail
 la t1, main_end
 bgeu t0, t1, fail
 li t0, {ordinary}
 sw zero, 0(t0)
 csrw mie, zero
 addi s3, s3, 1
 li t0, 1
 bne s3, t0, fail
 mret
'''
                else:code+=' j fail\n'
                code+=TAIL+f'''.section .nmi,"ax"
.balign 4
rnmi_handler:
 li s4, 1
 csrr t0, 0x742
 li t1, {(1<<63)|cause}
 bne t0, t1, rnmi_fail
 csrr s2, 0x741
 la t1, rnmi_wait
 bne s2, t1, rnmi_fail
 csrr t0, 0x744
 andi t1, t0, 8
 bnez t1, rnmi_fail
 srli t0, t0, 11
 andi t0, t0, 3
 li t1, {dict(M=3,S=1,U=0)[mode]}
 bne t0, t1, rnmi_fail
 csrw pmpcfg0, zero
 csrw pmpaddr6, zero
 li t0, -1
 csrw pmpaddr7, t0
 la t0, protected_data
 srli t0, t0, 2
 ori t0, t0, 1
 csrw pmpaddr0, t0
 li t0, {(15<<56)|24}
 csrw pmpcfg0, t0
 li t0, 0x1800
 csrc mstatus, t0
 li t0, 0x20000
 csrs mstatus, t0
 la t0, protected_data
 lw t1, 0(t0)
 li t0, 42
 bne t0, t1, rnmi_fail
'''
                if pending:
                    code+=f' li t0, 8\n csrw mie, t0\n csrsi mstatus, 8\n li t0, {ordinary}\n li t1, 1\n sw t1, 0(t0)\n'
                if nested:code+='nested_ecall:\n ecall\n'
                code+=f''' csrr t0, 0x741
 bne t0, s2, rnmi_fail
 csrr t0, 0x742
 li t1, {(1<<63)|cause}
 bne t0, t1, rnmi_fail
 csrr t0, 0x744
 andi t0, t0, 8
 bnez t0, rnmi_fail
 li s0, 1
 li s4, 0
 .word 0x70200073
rnmi_fail:
 la t0, fail
 jr t0
.section .data
.balign 16
protected_data: .word 42,0,0,0
.balign 8
.globl stimulus_step,stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
                if 'h' in config['isa'].split('_')[0][4:]:
                    code=code.replace(' srli t0, t0, 11\n',' andi t1, t0, 128\n bnez t1, rnmi_fail\n srli t0, t0, 11\n',1)
                links=[f'-Wl,--section-start=.nmi={vector:#x}']
                if exception_vector is not None:
                    code+=' .section .rnmi_exception,"ax"\n.balign 4\n la t0, normal_handler\n jr t0\n'
                    links.append(f'-Wl,--section-start=.rnmi_exception={exception_vector:#x}')
                name=f'rnmi-entry-{mode.lower()}-{int(nested)}-{int(pending)}'
                rows.append(dict(id=name,family='nmi',assembly=code,bins=[name],spec=SPEC,
                    spec_version=VERSION,link_options=links,events=[dict(step=1,kind='nmi',cause=cause,when_pc='rnmi_wait')],
                    reference_model=dict(kind='rnmi',mode=mode,cause=cause,nested=nested,pending=pending),
                    reference_unavailable='Spike has no external RNMI entry model or project RNMI exception vector'))
    return rows


def return_programs(config):
    rows=[]
    for mode in ('M','S','U'):
        for enable in (False,True):
            code=head(config)+f''' la t0, handler
 csrw mtvec, t0
 li s1, 0x12345
 csrr s5, 0x744
 andi s5, s5, 8
 li t0, {dict(M=3,S=1,U=0)[mode]<<11 | (8 if enable else 0)}
 csrw 0x744, t0
 csrr t1, 0x744
 andi t1, t1, 8
'''
            code+=' li s5, 8\n' if enable else ''
            code+=f''' bne t1, s5, fail
 csrci 0x744, 8
 csrr t1, 0x744
 andi t1, t1, 8
 bne t1, s5, fail
 la t0, resumed
 csrw 0x741, t0
 li t0, 0x1800
 csrc mstatus, t0
 li t0, 0x20000
 csrs mstatus, t0
 .word 0x70200073
resumed:
 ecall
 j fail
handler:
 csrr t0, mcause
 li t1, {dict(M=11,S=9,U=8)[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, resumed
 bne t0, t1, fail
 csrr t0, 0x741
 bne t0, t1, fail
 csrr t0, 0x744
 andi t0, t0, 8
 beqz t0, fail
 csrr t0, mstatus
 li t1, 0x20000
 and t0, t0, t1
 li t1, {0x20000 if mode=='M' else 0}
 bne t0, t1, fail
 li t0, 0x12345
 bne s1, t0, fail
 j pass
'''+TAIL
            if 'h' in config['isa'].split('_')[0][4:]:
                code=code.replace(' csrr t0, mstatus\n',' csrr t0, 0x744\n andi t0, t0, 128\n bnez t0, fail\n csrr t0, mstatus\n li t1, 1\n slli t1, t1, 39\n and t0, t0, t1\n bnez t0, fail\n csrr t0, mstatus\n',1)
            name=f'mnret-{mode.lower()}-{int(enable)}'
            rows.append(dict(id=name,family='nmi',assembly=code,bins=[name],spec=SPEC,spec_version=VERSION))
    return rows


def reference(scenario):
    plan=scenario['reference_model'];m=State(mode=plan['mode'],pc='rnmi_wait')
    m.write_nmie(True);m.entry(plan['cause'],'rnmi_handler');saved=dict(m.frame)
    m.mprv=True;ignored=not m.effective_mprv
    if plan['nested']:m.normal_exception('project RNMI exception vector')
    frame_preserved=m.frame==saved;masked=not m.nmie
    m.ret()
    actual=dict(mode=m.mode,pc=m.pc,nmie=m.nmie,mprv=m.mprv)
    expected=dict(mode=plan['mode'],pc='rnmi_wait',nmie=True,mprv=plan['mode']=='M')
    return dict(id=scenario['id'],status='pass' if actual==expected and ignored and frame_preserved and masked else 'fail',
                evidence='model-based',actual=actual,expected=expected,ordinary_irq_masked=masked,
                frame_preserved=frame_preserved,mprv_ignored_during_entry=ignored)
