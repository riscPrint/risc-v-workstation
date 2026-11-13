"""Independent checks before dependency annotations enter memory-order search."""
from rvw.common.riscv import integer_sources, decode


class DeclarationError(ValueError):
    status = "error"


def validate_declarations(events, initial):
    by_id = {e['id']: e for e in events}
    for e in events:
        for name in ('addr', 'data', 'ctrl'):
            for identity in e[name]:
                source = by_id.get(identity)
                if source is None or source['hart'] != e['hart'] or source['order'] >= e['order']:
                    raise DeclarationError('dependency violates per-hart program order')
        if 'read_from' not in e:
            continue
        if e['kind'] not in ('R', 'LR', 'AMO'):
            raise DeclarationError('read_from requires a read event')
        identity = e['read_from']
        location = e['address'], e['size']
        if identity == f'initial:{location[0]}:{location[1]}':
            value = initial.get(location)
        else:
            source = by_id.get(identity)
            if source is None or source['kind'] not in ('W', 'SC', 'AMO'):
                raise DeclarationError('read_from does not name a store')
            if source is e or (source['hart'] == e['hart'] and source['order'] >= e['order']):
                raise DeclarationError('read_from violates per-hart program order')
            if (source['address'], source['size']) != location:
                raise DeclarationError('read_from location differs')
            value = source['write']
        if value != e['read']:
            raise DeclarationError('read_from value differs from observed store')


def validate_register_dependencies(records, xlen):
    """Track observed integer dataflow, independently of memory_model edges.

    The check covers scalar address and store-data dependencies. It does not
    infer FP/vector dataflow. Control dependencies use observed scalar branches and JALR.
    """
    registers, values, controls, last_order = {}, {}, {}, {}
    for row in records:
        if 'event' in row:
            if row['event'] == 'reset':
                registers[row['hart']] = {}
                values[row['hart']] = {0: 0}
                controls[row['hart']] = set()
                last_order.pop(row['hart'], None)
            continue
        hart, order = row['hart'], int(row['order'])
        if order <= last_order.get(hart, -1):
            raise DeclarationError('observed per-hart program order is not increasing')
        last_order[hart] = order
        regs = registers.setdefault(hart, {})
        observed = values.setdefault(hart, {0: 0})
        insn = row['insn']
        info = decode(insn, xlen)
        if info.cls == 'unknown' or info.dest_bank == 'f' or any(bank != 'x' for bank, _ in info.sources):
            return 'independent dependency check supports decoded scalar integer dataflow only'
        if info.cls == 'csr' and not (insn >> 20 == 0xf14 and (insn >> 12) & 7 == 2 and (insn >> 15) & 31 == 0):
            return 'independent dependency check does not track mutable CSR dataflow'
        rs1, rs2 = integer_sources(insn, xlen)
        for index, register in enumerate((rs1, rs2), 1):
            field = f'rs{index}_rdata'
            if field in row and register in observed and row[field] != observed[register]:
                raise DeclarationError('observed register value violates per-hart program order')
        a, b = set(regs.get(rs1, ())), set(regs.get(rs2, ()))
        control = controls.setdefault(hart, set())
        if info.cls in ('branch', 'jump'):
            control.update(a | b)
        e = row.get('memory_model')
        if e and e['kind'] != 'FENCE':
            if not control <= set(e.get('ctrl', ())):
                raise DeclarationError('declared control dependencies omit observed register dataflow')
            if not a <= set(e.get('addr', ())):
                raise DeclarationError('declared address dependencies omit observed register dataflow')
            if e['kind'] in ('W', 'SC', 'AMO') and not b <= set(e.get('data', ())):
                raise DeclarationError('declared data dependencies omit observed register dataflow')
        if row.get('trap'):
            continue
        if e and e['kind'] in ('R', 'LR', 'AMO') and row.get('rd') and 'rd_wdata' in row:
            bits = 8 * e['size']
            value = row['mem_rdata'] & ((1 << bits)-1)
            signed = insn & 127 == 0x2f or ((insn >> 12) & 7) < 4
            if signed and value & (1 << (bits-1)):
                value -= 1 << bits
            if row['rd_wdata'] != value & ((1 << xlen)-1):
                raise DeclarationError('observed load result differs from memory value')
        rd = row.get('rd', 0)
        if rd and 'rd_wdata' in row:
            observed[rd] = row['rd_wdata']
        failed_sc = insn & 127 == 0x2f and insn >> 27 == 3 and not row.get('mem_wmask')
        if rd and not failed_sc:
            sources = a | b
            if e and e['kind'] in ('R', 'LR', 'AMO', 'SC'):
                # A load produces its own memory value. Its input dependencies
                # are represented separately by the event's address edges.
                sources = {e['id']}
            if info.cls == 'jump' or insn & 127 in (0x37, 0x17, 0x73):
                sources = set()
            if info.dest_bank == 'x':
                regs[rd] = sources
