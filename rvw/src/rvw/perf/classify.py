"""Optional label interpretation. The parser itself remains ISA independent."""
import re


# Finite mnemonic sets keep unrelated extensions out of prefix-based classes.
_CLASSES = {
    'multiply': set('mul mulh mulhsu mulhu mulw'.split()),
    'divide': set('div divu divw divuw rem remu remw remuw'.split()),
    'load': set('lb lbu lh lhu lw lwu ld flh flw fld flq'.split()),
    'store': set('sb sh sw sd fsh fsw fsd fsq'.split()),
    'control': set(('beq bne blt bge bltu bgeu beqz bnez blez bgez bltz bgtz '
                    'bgt ble bgtu bleu j jr jal jalr ret call tail').split()),
    'system': set(('csrrw csrrs csrrc csrrwi csrrsi csrrci csrr csrw csrs csrc csrwi csrsi csrci '
                   'fence fence.i fence.tso pause sfence.vma hfence.vvma hfence.gvma '
                   'ecall ebreak mret sret uret dret wfi '
                   'frcsr fscsr frrm fsrm fsrmi frflags fsflags fsflagsi').split()),
    'integer': set(('add addw sub subw sll sllw slt sltu xor srl srlw sra sraw or and '
                    'addi addiw slli slliw slti sltiu xori srli srliw srai sraiw ori andi lui auipc '
                    'nop li la lla lga mv neg negw not sext.w seqz snez sltz sgtz '
                    'bclr bclri bext bexti binv binvi bset bseti '
                    'andn orn xnor clz clzw ctz ctzw cpop cpopw min minu max maxu '
                    'sext.b sext.h zext.b zext.h zext.w rol rolw ror rorw rori roriw orc.b rev8 '
                    'sh1add sh2add sh3add sh1add.uw sh2add.uw sh3add.uw add.uw slli.uw '
                    'clmul clmulh clmulr').split()),
    'floating': set(),
    'atomic': set(),
}
for _cls, _ops in {
    'integer': 'addi4spn nop addi addiw li addi16sp lui srli srai andi sub xor or and subw addw slli mv add',
    'load': 'fld lw ld flw fldsp lwsp flwsp ldsp',
    'store': 'fsd sw sd fsw fsdsp swsp fswsp sdsp',
    'control': 'j jal beqz bnez jr jalr',
    'system': 'ebreak',
}.items():
    _CLASSES[_cls].update('c.' + op for op in _ops.split())
for _fmt in ('h', 's', 'd', 'q'):
    _CLASSES['floating'].update(op + '.' + _fmt for op in (
        'fadd fsub fmul fdiv fsqrt fsgnj fsgnjn fsgnjx fmin fmax '
        'fle flt feq fclass fmadd fmsub fnmsub fnmadd fmv fabs fneg').split())
    for _other in ('h', 's', 'd', 'q', 'w', 'wu', 'l', 'lu'):
        if _fmt != _other:
            _CLASSES['floating'].update((f'fcvt.{_fmt}.{_other}', f'fcvt.{_other}.{_fmt}'))
_CLASSES['floating'].update('fmv.x.h fmv.h.x fmv.x.w fmv.w.x fmv.x.d fmv.d.x'.split())
for _op in 'amoadd amoswap amoxor amoor amoand amomin amomax amominu amomaxu lr sc'.split():
    for _width in ('w', 'd'):
        _CLASSES['atomic'].update(f'{_op}.{_width}{suffix}' for suffix in ('', '.aq', '.rl', '.aqrl'))
MNEMONIC_CLASSES = {op: cls for cls, ops in _CLASSES.items() for op in ops}


def identify(labels: dict[str, str], isa: str) -> tuple[str, str]:
    label = labels.get("0", "")
    pc_match = re.match(r"(?:0x)?([0-9a-fA-F]+)(?::|\s)", label)
    pc = hex(int(pc_match[1], 16)) if pc_match else "unknown"
    explicit = re.search(r"\bclass=([\w.-]+)", " ".join(labels.values()))
    if explicit:
        return pc, explicit[1]
    if isa != "riscv" or not pc_match:
        return pc, "unknown"
    text = label[pc_match.end():].strip()
    # Labels may contain an encoded word before the assembly mnemonic.
    text = re.sub(r"^[0-9a-fA-F]{4,8}\s+", "", text)
    op = text.split()[0].lower() if text else ""
    return pc, MNEMONIC_CLASSES.get(op, 'unknown')
