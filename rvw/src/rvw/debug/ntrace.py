"""N-Trace (Nexus-based) instruction trace: reference encoder from C2 and a decoder.

Separate from E-Trace: an E-Trace result never counts as N-Trace support.

Codec `rvw-ntrace/1`. The message layout follows the N-Trace/IEEE-5001 rules: each
byte carries six MDO bits and two MSEO bits (0 normal, 1 end of a variable field, 3 end
of message). Fields are packed LSB first; a variable field ends on a byte boundary.
Addresses are halfword addresses: sync messages carry FADDR, others UADDR (XOR with the
last address). ICNT counts 16-bit units. HIST holds branch outcomes after a leading 1.

Messages (TCODE): DirectBranch 3, IndirectBranch 4, Error 8, ProgTraceSync 9,
ResourceFull 27, IndirectBranchHist 28, ProgTraceCorrelation 33, Ownership 2.
Modes: `btm` (branch messages for every taken direct branch) and `htm` (history).
SYNC, EVCODE, ETYPE, RCODE and BTYPE values are profile parameters with the defaults
below. Check them against the encoder's documentation before a conformance claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rvw.common.riscv import decode as decode_instruction

CODEC = 'rvw-ntrace/1'
TCODES = {'Ownership': 2, 'DirectBranch': 3, 'IndirectBranch': 4, 'Error': 8, 'ProgTraceSync': 9,
          'ResourceFull': 27, 'IndirectBranchHist': 28, 'ProgTraceCorrelation': 33}
NAMES = {v: k for k, v in TCODES.items()}
DEFAULTS = dict(mode='htm', src_bits=0, hist_bits=31, icnt_bits=22, sync_period=0, ownership=True,
                sync_start=1, sync_restart=2, sync_periodic=5, evcode_stop=4, etype_overflow=0,
                rcode_icnt=0, rcode_hist=1, btype_indirect=0, btype_trap=1)

# Field layout: (name, kind) with kind an int (fixed bits) or 'var'.
LAYOUT = {
    'Ownership': [('process', 'var')],
    'DirectBranch': [('icnt', 'var')],
    'IndirectBranch': [('btype', 2), ('icnt', 'var'), ('uaddr', 'var')],
    'Error': [('etype', 4), ('ecode', 'var')],
    'ProgTraceSync': [('sync', 4), ('icnt', 'var'), ('faddr', 'var')],
    'ResourceFull': [('rcode', 4), ('rdata', 'var')],
    'IndirectBranchHist': [('btype', 2), ('icnt', 'var'), ('uaddr', 'var'), ('hist', 'var')],
    'ProgTraceCorrelation': [('evcode', 4), ('cdf', 2), ('icnt', 'var'), ('hist', 'var')],
}


@dataclass
class Message:
    name: str
    fields: dict = field(default_factory=dict)
    src: int = 0

    def as_dict(self):
        return {'tcode': self.name, 'src': self.src, **self.fields}


# -- bit packing ---------------------------------------------------------------------------
class _Writer:
    def __init__(self):
        self.bytes = bytearray()
        self.bits = 0       # bits used in the current MDO group
        self.mdo = 0

    def fixed(self, value, width):
        for i in range(width):
            self._bit((value >> i) & 1)

    def _bit(self, bit):
        self.mdo |= bit << self.bits
        self.bits += 1
        if self.bits == 6:
            self.bytes.append(self.mdo << 2)
            self.mdo = self.bits = 0

    def var(self, value, end):
        width = max(1, value.bit_length())
        self.fixed(value, width)
        if self.bits:
            self.bytes.append(self.mdo << 2)
            self.mdo = self.bits = 0
        self.bytes[-1] |= 3 if end else 1


def pack(messages, profile):
    out = bytearray()
    for message in messages:
        writer = _Writer()
        writer.fixed(TCODES[message.name], 6)
        writer.fixed(message.src, profile['src_bits'])
        layout = LAYOUT[message.name]
        last_var = max(i for i, (_, kind) in enumerate(layout) if kind == 'var')
        for index, (name, kind) in enumerate(layout):
            value = message.fields.get(name, 0)
            if kind == 'var':
                writer.var(value, index == last_var)
            else:
                writer.fixed(value, kind)
        out += writer.bytes
    return bytes(out)


def unpack(data, profile):
    """Bytes to messages. Raises ValueError on malformed framing. A trailing partial message
    is returned separately so a cut stream is reported, never decoded as complete."""
    messages, current = [], []
    for byte in data:
        current.append(byte)
        if byte & 3 == 3:
            messages.append(_parse(current, profile))
            current = []
    return messages, len(current)


def _parse(chunk, profile):
    groups, ends = [], []
    for byte in chunk:
        groups.append(byte >> 2)
        ends.append(byte & 3)
    bits = []
    for g in groups:
        bits += [(g >> i) & 1 for i in range(6)]
    position = 0
    def take(width):
        nonlocal position
        value = sum(bits[position + i] << i for i in range(width))
        position += width
        return value
    def take_var():
        # A variable field may start inside a group after fixed fields; it ends with the
        # first group whose MSEO marks an end.
        end = position // 6
        while end < len(ends) and ends[end] == 0:
            end += 1
        if end >= len(ends):
            raise ValueError('variable field without an end marker')
        return take((end + 1) * 6 - position)
    tcode = take(6)
    if tcode not in NAMES:
        raise ValueError(f'unknown TCODE {tcode}')
    name = NAMES[tcode]
    src = take(profile['src_bits'])
    fields = {}
    layout = LAYOUT[name]
    for index, (fname, kind) in enumerate(layout):
        if kind == 'var':
            fields[fname] = take_var()
        else:
            fields[fname] = take(kind)
    return Message(name, fields, src)


# -- instruction helpers -----------------------------------------------------------------------
def _sx(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def direct_target(insn, pc):
    """Target of a direct branch or jump, or None. Compressed forms use the 16-bit encoding."""
    if insn & 3 != 3:
        op, f3 = insn & 3, (insn >> 13) & 7
        if op == 1 and f3 in (1, 5):    # c.jal (RV32) / c.j
            b = insn >> 2
            imm = (((b >> 10) & 1) << 11 | ((b >> 9) & 1) << 4 | ((b >> 7) & 3) << 8 | ((b >> 6) & 1) << 10
                   | ((b >> 5) & 1) << 6 | ((b >> 4) & 1) << 7 | ((b >> 1) & 7) << 1 | (b & 1) << 5)
            return pc + _sx(imm, 12)
        if op == 1 and f3 in (6, 7):    # c.beqz / c.bnez
            imm = (((insn >> 12) & 1) << 8 | ((insn >> 10) & 3) << 3 | ((insn >> 5) & 3) << 6
                   | ((insn >> 3) & 3) << 1 | ((insn >> 2) & 1) << 5)
            return pc + _sx(imm, 9)
        return None
    opcode = insn & 0x7f
    if opcode == 0x6f:
        imm = ((insn >> 31) << 20) | (((insn >> 12) & 0xff) << 12) | (((insn >> 20) & 1) << 11) | (((insn >> 21) & 0x3ff) << 1)
        return pc + _sx(imm, 21)
    if opcode == 0x63:
        imm = ((insn >> 31) << 12) | (((insn >> 7) & 1) << 11) | (((insn >> 25) & 0x3f) << 5) | (((insn >> 8) & 15) << 1)
        return pc + _sx(imm, 13)
    return None


def kind_of(insn, xlen=64):
    d = decode_instruction(insn, xlen)
    if d.mnemonic == 'unknown':
        return 'unknown', d.length
    if d.cls == 'branch':
        return 'branch', d.length
    if d.mnemonic in ('jal', 'c.j', 'c.jal'):
        return 'jump', d.length
    if d.mnemonic in ('jalr', 'c.jr', 'c.jalr', 'mret', 'sret', 'uret'):
        return 'indirect', d.length
    return 'plain', d.length


# -- encoder ------------------------------------------------------------------------------------
def normalize(profile=None):
    p = {**DEFAULTS, **(profile or {})}
    if p['mode'] not in ('btm', 'htm'):
        raise ValueError('N-Trace mode must be btm or htm')
    if set(p) - set(DEFAULTS):
        raise ValueError(f'unknown N-Trace keys: {", ".join(sorted(set(p) - set(DEFAULTS)))}')
    return p


def encode(rows, profile=None, *, xlen=64):
    """Messages for one qualified window of C2 rows (see etrace_flow.retirement)."""
    p = normalize(profile)
    if not rows:
        return []
    msgs = []
    last = [None]
    icnt = 0
    hist = 1
    count_since_sync = 0

    def addr_msg(name, target, **fields):
        nonlocal icnt, hist, count_since_sync
        fields['icnt'] = icnt
        if name in ('IndirectBranch', 'IndirectBranchHist'):
            fields['uaddr'] = (target >> 1) ^ (last[0] >> 1)
        if name == 'IndirectBranchHist':
            fields['hist'] = hist
        msgs.append(Message(name, fields))
        last[0] = target
        icnt, hist = 0, 1
        count_since_sync += 1

    def flush_hist():
        nonlocal hist
        if hist.bit_length() - 1 >= p['hist_bits']:
            msgs.append(Message('ResourceFull', {'rcode': p['rcode_hist'], 'rdata': hist}))
            hist = 1

    first = rows[0]
    if p['ownership']:
        msgs.append(Message('Ownership', {'process': first['mode']}))
    msgs.append(Message('ProgTraceSync', {'sync': p['sync_start'], 'icnt': 0, 'faddr': first['pc'] >> 1}))
    last[0] = first['pc']
    mode = first['mode']
    for index, row in enumerate(rows):
        if 'irq' in row and index:
            addr_msg('IndirectBranchHist' if p['mode'] == 'htm' else 'IndirectBranch', row['pc'],
                     btype=p['btype_trap'])
        if p['ownership'] and row['mode'] != mode and not row.get('trap'):
            msgs.append(Message('Ownership', {'process': row['mode']}))
        mode = row['mode']
        if row.get('trap'):
            addr_msg('IndirectBranchHist' if p['mode'] == 'htm' else 'IndirectBranch', row['pc_next'],
                     btype=p['btype_trap'])
            continue
        kind, length = kind_of(row['insn'], xlen)
        if kind == 'unknown':
            raise ValueError(f'unknown instruction at 0x{row["pc"]:x}')
        icnt += length // 2
        taken = row['pc_next'] != row['pc'] + length
        if kind == 'branch':
            if p['mode'] == 'htm':
                hist = (hist << 1) | int(taken)
                flush_hist()
            elif taken:
                addr_msg('DirectBranch', row['pc_next'])
        elif kind == 'jump' and p['mode'] == 'btm':
            addr_msg('DirectBranch', row['pc_next'])
        elif kind == 'indirect':
            addr_msg('IndirectBranchHist' if p['mode'] == 'htm' else 'IndirectBranch', row['pc_next'],
                     btype=p['btype_indirect'])
            if p['sync_period'] and count_since_sync >= p['sync_period'] and index + 1 < len(rows):
                msgs.append(Message('ProgTraceSync', {'sync': p['sync_periodic'], 'icnt': 0,
                                                      'faddr': rows[index + 1]['pc'] >> 1}))
                count_since_sync = 0
        if icnt >= 1 << p['icnt_bits']:
            # Supply branch outcomes before asking the decoder to walk this count.
            if hist != 1:
                msgs.append(Message('ResourceFull', {'rcode': p['rcode_hist'], 'rdata': hist}))
                hist = 1
            msgs.append(Message('ResourceFull', {'rcode': p['rcode_icnt'], 'rdata': icnt}))
            icnt = 0
    msgs.append(Message('ProgTraceCorrelation', {'evcode': p['evcode_stop'], 'cdf': 1, 'icnt': icnt, 'hist': hist}))
    return msgs


def encode_windows(windows, profile=None, *, xlen=64):
    out = []
    for window in windows:
        out += encode(window, profile, xlen=xlen)
    return out


# -- decoder ------------------------------------------------------------------------------------
class Code:
    """Instruction memory from ELF segments: (address, bytes) pairs."""

    def __init__(self, segments):
        self.segments = list(segments)

    def insn(self, pc):
        for base, data in self.segments:
            if base <= pc < base + len(data) - 1:
                low = int.from_bytes(data[pc - base:pc - base + 2], 'little')
                if low & 3 != 3:
                    return low
                if pc + 4 > base + len(data):
                    break
                return int.from_bytes(data[pc - base:pc - base + 4], 'little')
        raise ValueError(f'no code at 0x{pc:x}')


def decode(messages, code, profile=None, *, xlen=64):
    """Messages to segments of decoded PCs. A segment ends at an Error message, a stream end
    or a decode failure. Execution between segments is unknown. Returns list of
    (pcs, ended_cleanly, reason)."""
    p = normalize(profile)
    segments, pcs = [], []
    pc = None
    hist_bits = []

    def run(units, *, last_taken=False):
        """Walk `units` halfwords. In BTM only a DirectBranch run ends at a taken branch."""
        nonlocal pc
        while units > 0:
            insn = code.insn(pc)
            kind, length = kind_of(insn, xlen)
            if kind == 'unknown':
                raise ValueError(f'unknown instruction at 0x{pc:x}')
            pcs.append(pc)
            units -= length // 2
            if units < 0:
                raise ValueError('ICNT ends inside an instruction')
            last_one = units == 0
            if kind == 'branch':
                if p['mode'] == 'htm':
                    if not hist_bits:
                        raise ValueError('branch without a history bit')
                    taken = hist_bits.pop(0)
                else:
                    taken = last_one and last_taken
                pc = direct_target(insn, pc) if taken else pc + length
            elif kind == 'jump':
                pc = direct_target(insn, pc)
            elif kind == 'indirect':
                if not last_one:
                    raise ValueError(f'indirect jump at 0x{pc:x} inside an ICNT run')
                pc = None
            else:
                pc = pc + length
        return pc

    def end(reason, clean):
        nonlocal pcs, pc
        if pcs:
            segments.append((pcs, clean, reason))
        pcs, pc = [], None

    def hist_list(value):
        if value <= 0:
            raise ValueError('HIST without a stop bit')
        return [(value >> i) & 1 for i in range(value.bit_length() - 2, -1, -1)]

    for message in messages:
        f = message.fields
        try:
            if message.name == 'Error':
                end('error message (trace loss)', False)
                continue
            if message.name == 'ProgTraceSync':
                if pc is not None and f['icnt']:
                    run(f['icnt'])
                if f['sync'] == p['sync_periodic'] and pc is not None and pc != f['faddr'] << 1:
                    raise ValueError('periodic sync address disagrees with the decoded flow')
                if f['sync'] != p['sync_periodic'] and pcs:
                    end('restart', True)
                pc = f['faddr'] << 1
                last = pc
                hist_bits = []
                continue
            if pc is None and message.name not in ('Ownership',):
                continue   # not synchronized: wait for ProgTraceSync
            if message.name == 'Ownership':
                continue
            if message.name == 'ResourceFull':
                if f['rcode'] == p['rcode_hist']:
                    hist_bits += hist_list(f['rdata'])
                elif f['rcode'] == p['rcode_icnt']:
                    run(f['rdata'])
                continue
            if message.name == 'DirectBranch':
                run(f['icnt'], last_taken=True)
                last = pc
            elif message.name in ('IndirectBranch', 'IndirectBranchHist'):
                if message.name == 'IndirectBranchHist':
                    hist_bits += hist_list(f['hist'])
                trap = f['btype'] == p['btype_trap']
                if f['icnt']:
                    pending = run(f['icnt'])
                    if pending is not None and not trap:
                        raise ValueError('IndirectBranch ICNT does not end at an indirect jump')
                target = ((last >> 1) ^ f['uaddr']) << 1
                pc, last = target, target
                hist_bits = []
            elif message.name == 'ProgTraceCorrelation':
                if f.get('cdf') == 1:
                    hist_bits += hist_list(f['hist'])
                run(f['icnt'])
                end('trace stop', True)
        except ValueError as exc:
            end(f'decode failure: {exc}', False)
    end('stream end without a stop message', False)
    return segments
