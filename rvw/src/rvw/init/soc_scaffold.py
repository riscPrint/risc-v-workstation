"""Translate a single declared memory bus to the existing SimpleCpuBus bridge."""
import json


def wrapper(core):
    if core['top']['kind'] != 'spinal' or core['xlen'] != 32 or len(core['buses']) != 1:
        raise ValueError('SoC wrapper needs one mapped RV32 Spinal memory bus')
    b=core['buses'][0]
    if b['protocol'] != 'req-rsp' or 'rsp_ready' in b['signals']:
        raise ValueError('SoC wrapper needs single-outstanding req-rsp without rsp_ready')
    s=b['signals'];q=json.dumps
    lines=['package rvwproject','import spinal.core._','import spinal.lib._','import rvwsoc._',
           'class RvwProjectCore extends Component with SimpleCoreWrapper {',
           ' val io = new Bundle {', '  val bus = master(SimpleCpuBus())',
           '  val interrupts = in Bits(32 bits)', '  val debugReset = in Bool()', ' }',
           ' def bus = io.bus', ' def interrupts = io.interrupts', ' def debugReset = io.debugReset',
           f' val cpu = Class.forName({q(core["top"]["class"])}).getDeclaredConstructor().newInstance().asInstanceOf[Component]',
           ' val wiring = this.rework {',
           ' val pins = cpu.getAllIo.map(p => p.getName() -> p).toMap',
           ' def bits(n: String) = pins(n).asBits',
           ' def drive(n: String, value: Bits): Unit = pins(n).assignFromBits(value)',
           ' val pending = Reg(Bool()) init(False)',
           ' val address = Reg(UInt(32 bits))', ' val data = Reg(Bits(32 bits))',
           ' val mask = Reg(Bits(4 bits))', ' val write = Reg(Bool())',
           ' io.bus.valid := pending', ' io.bus.address := address', ' io.bus.wdata := data',
           ' io.bus.mask := mask', ' io.bus.write := write',
           f' when(!pending && bits({q(s["cmd_valid"])}).asBool) {{',
           f'  address := bits({q(s["address"])}).asUInt',
           f'  data := '+(f'bits({q(s["wdata"])})' if 'wdata' in s else 'B(0,32 bits)'),
           f'  mask := '+(f'bits({q(s["mask"])})' if 'mask' in s else 'B(15,4 bits)'),
           f'  write := '+(f'bits({q(s["write"])}).asBool' if 'write' in s else 'False'),
           '  pending := True', ' }', ' when(pending && io.bus.ready) { pending := False }']
    if core.get('rvfi'):
        from .mapped import RVFI_FIELDS
        declarations=[]
        for field in RVFI_FIELDS:
            width=64 if field=='order' else 1 if field in ('valid','trap','halt','intr') else 2 if field=='mode' else 5 if field.endswith('_addr') and field!='mem_addr' else 4 if field in ('mem_rmask','mem_wmask') else 32
            declarations.append(f'  val rvfi_{field} = out(Bits({width} bits))')
        lines[lines.index(' }'):lines.index(' }')] = declarations
        for field in RVFI_FIELDS:
            lines.append(f' io.rvfi_{field} := bits({q(core["rvfi"]["prefix"]+field)})')
    drives={'cmd_ready':'(!pending).asBits','rsp_valid':
            '(pending && io.bus.ready'+('' if b['write_response'] else ' && !write')+').asBits',
            'rdata':'io.bus.rdata','error':'io.bus.error.asBits'}
    for k,v in drives.items():
        if k in s: lines.append(f' drive({q(s[k])}, {v})')
    for bit,pin in core.get('irq',{}).items():
        lines.append(f' drive({q(pin)}, io.interrupts({bit}).asBits)')
    for pin,value in core['constants'].items():
        lines.append(f' drive({q(pin)}, B(BigInt({q(str(value).removeprefix("0x"))},16), pins({q(pin)}).getBitsWidth bits))')
    lines += [' when(io.debugReset) { pending := False }',' }','}']
    return '\n'.join(lines)+'\n'
