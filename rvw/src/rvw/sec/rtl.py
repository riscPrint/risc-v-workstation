"""Native Verilator harness for a core's exported Verilog with simple valid/ready buses.

A project binding (`rvw.sec-core/1`) names the RTL, clock, reset, buses and the retirement
source. The harness owns RAM, a per-word taint shadow of RAM, in-order bus responses, C2
capture and cycle-stamped observations. It names no core signal itself.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from rvw.cosim.elf import Elf
from .common import native

SCHEMA = 'rvw.sec-core/1'
RVFI = ('valid', 'order', 'insn', 'trap', 'mode', 'rd_addr', 'rd_wdata', 'pc_rdata', 'pc_wdata',
        'mem_addr', 'mem_rmask', 'mem_wmask', 'mem_rdata', 'mem_wdata')
BUS_FIELDS = ('cmd_valid', 'cmd_ready', 'cmd_address', 'cmd_write', 'cmd_data', 'cmd_mask', 'cmd_size',
              'cmd_id', 'rsp_valid', 'rsp_data', 'rsp_error', 'rsp_id')
SIMPLE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def number(v):
    return int(v, 0) if isinstance(v, str) else int(v)


def load(path):
    """Read a binding. Paths may use environment variables and are relative to the file."""
    path = Path(path).resolve()
    b = json.loads(path.read_text())
    if b.get('schema') != SCHEMA:
        raise ValueError(f'binding schema must be {SCHEMA}')
    def where(p):
        text = os.path.expandvars(p)
        if '$' in text:
            raise ValueError(f'unset environment variable in {p}')
        q = Path(text)
        return (q if q.is_absolute() else path.parent/q).resolve()
    b['rtl'] = [where(p) for p in b['rtl']]
    for k in ('platform',):
        if b.get(k):
            b[k] = where(b[k])
    b['_dir'] = path.parent
    for k in ('top', 'clock', 'reset'):
        if not SIMPLE.fullmatch(b.get(k, '')):
            raise ValueError(f'binding needs a simple {k} name')
    b['ram_base'] = number(b['ram']['base']); b['ram_size'] = number(b['ram']['size'])
    if b['ram_size'] % 4 or b['ram_size'] > 1 << 26:
        raise ValueError('RAM size must be word aligned and at most 64 MiB')
    for bus in b['buses']:
        if bus.get('kind') not in ('fetch', 'data') or not SIMPLE.fullmatch(bus.get('name', '')):
            raise ValueError('each bus needs a name and kind fetch or data')
        for f in ('cmd_valid', 'cmd_address', 'rsp_valid', 'rsp_data'):
            if f not in bus:
                raise ValueError(f'bus {bus["name"]} needs {f}')
    if b['retire'].get('kind') not in ('rvfi', 'commit'):
        raise ValueError('retire kind must be rvfi or commit')
    return b


def ports(binding):
    """Top-level ANSI port list: name -> (direction, width)."""
    text = '\n'.join(p.read_text() for p in binding['rtl'])
    m = re.search(r'\bmodule\s+'+re.escape(binding['top'])+r'\s*\((.*?)\);', text, re.S)
    if not m:
        raise ValueError('top module not found in RTL')
    found = {}
    for d, w, n in re.findall(r'\b(input|output)\s+(?:wire|reg|logic)?\s*(\[\s*\d+\s*:\s*0\s*\])?\s*([A-Za-z_]\w*)', m.group(1)):
        found[n] = (d, int(re.search(r'\d+', w).group())+1 if w else 1)
    return found


def image(elf, base, size):
    """Little-endian RAM words from ELF load segments. Out-of-RAM bytes are an error."""
    e = Elf(elf)
    if e.xlen != 32:
        raise ValueError('the native security harness supports RV32 ELFs')
    mem = bytearray(size)
    for addr, data, memsz in e.segments:
        if addr < base or addr+memsz > base+size:
            raise ValueError('ELF segment outside binding RAM')
        mem[addr-base:addr-base+len(data)] = data
    tohost = e.symbols.get('tohost')
    if tohost is None:
        raise ValueError('ELF needs a tohost symbol')
    return mem, tohost, e.entry


def hexwords(mem):
    return '\n'.join(f'{int.from_bytes(mem[i:i+4], "little"):08x}' for i in range(0, len(mem), 4))+'\n'


def testbench(binding, widths, ift=None):
    """SystemVerilog testbench text. `ift` is (prefix, sink list) for a shadow DUT."""
    clock, reset = binding['clock'], binding['reset']
    words = binding['ram_size']//4
    module = binding['top']+('__ift' if ift else '')
    L = ['`timescale 1ns/1ps', 'module rvw_sec_tb;',
         f'reg {clock} = 0;', 'integer cycle = 0, fd, done_at = -1, max_cycles;',
         f'reg [31:0] mem [0:{words-1}];', f'reg [31:0] taint [0:{words-1}];', 'reg [1023:0] path;',
         'reg [31:0] tohost_value = 0;', 'reg [31:0] tohost;', 'reg [1:0] last_priv = 2\'d3;']
    con = [f'.{clock}({clock})']
    ties = binding.get('ties', {})
    driven = {clock}
    for n, (d, w) in widths.items():
        if n == clock:
            continue
        L.append(f'{"reg" if d == "input" else "wire"} [{w-1}:0] {n};')
        con.append(f'.{n}({n})')
        if ift:
            L.append(f'{"reg" if d == "input" else "wire"} [{w-1}:0] {n}__t;')
            con.append(f'.{n}__t({n}__t)')
    L.append(f'{module} dut({", ".join(con)});')
    base = f"32'h{binding['ram_base']:08x}"
    def word(addr):
        return f'((({addr}) - {base}) >> 2)'
    L += ['function automatic integer inram(input [31:0] a);',
          f"  inram = (a >= {base}) && (a - {base} < 32'd{binding['ram_size']});", 'endfunction']
    # One FIFO per bus: responses in request order after `latency` cycles.
    for bus in binding['buses']:
        n = bus['name']; lat = int(bus.get('latency', 1)); depth = 16
        w_id = widths[bus['cmd_id']][1] if bus.get('cmd_id') else 1
        L += [f'reg [31:0] {n}_q_addr [0:{depth-1}]; reg {n}_q_err [0:{depth-1}]; reg [31:0] {n}_q_due [0:{depth-1}];',
              f'reg [31:0] {n}_q_data [0:{depth-1}]; reg [31:0] {n}_q_taint [0:{depth-1}];',
              f'reg [{w_id-1}:0] {n}_q_id [0:{depth-1}]; reg {n}_q_rsp [0:{depth-1}];',
              f'integer {n}_head = 0, {n}_tail = 0;']
        driven.add(bus['rsp_valid']); driven.add(bus['rsp_data'])
        for f in ('cmd_ready', 'rsp_error', 'rsp_id'):
            if bus.get(f):
                driven.add(bus[f])
    for n, (d, w) in widths.items():
        if d == 'input' and n not in driven and n != reset and n not in ties:
            ties[n] = 0
    # Drive inputs before each rising edge from state; sample outputs at the edge.
    L += [f'task automatic drive;', 'begin']
    for n, v in ties.items():
        L.append(f"  {n} = {widths[n][1]}'d{number(v)};")
    for bus in binding['buses']:
        n = bus['name']
        L += [f'  {bus["rsp_valid"]} = 0; {bus["rsp_data"]} = 0;']
        if bus.get('cmd_ready'):
            L.append(f'  {bus["cmd_ready"]} = 1;')
        if bus.get('rsp_error'):
            L.append(f'  {bus["rsp_error"]} = 0;')
        if bus.get('rsp_id'):
            L.append(f'  {bus["rsp_id"]} = 0;')
        if ift:
            L.append(f'  {bus["rsp_data"]}__t = 0;')
        # Skip queued requests that need no response (stores without a response channel).
        L += [f'  while ({n}_head != {n}_tail && !{n}_q_rsp[{n}_head % 16]) {n}_head = {n}_head + 1;',
              f'  if ({n}_head != {n}_tail && {n}_q_due[{n}_head % 16] <= cycle) begin',
              f'    {bus["rsp_valid"]} = 1;',
              f'    {bus["rsp_data"]} = {n}_q_data[{n}_head % 16];']
        if ift:
            L.append(f'    {bus["rsp_data"]}__t = {n}_q_taint[{n}_head % 16];')
        if bus.get('rsp_error'):
            L.append(f'    {bus["rsp_error"]} = {n}_q_err[{n}_head % 16];')
        if bus.get('rsp_id'):
            L.append(f'    {bus["rsp_id"]} = {n}_q_id[{n}_head % 16];')
        L.append('  end')
    if ift:
        for n, (d, w) in widths.items():
            if d == 'input' and n != clock and not any(n == b['rsp_data'] for b in binding['buses']):
                L.append(f"  {n}__t = 0;")
    L += ['end', 'endtask']
    # Observation and bus model at each rising edge (pre-edge values).
    L += [f'always @(posedge {clock}) if (!{reset}) begin']
    for bus in binding['buses']:
        n = bus['name']
        ready = bus.get('cmd_ready')
        fire = f'{bus["cmd_valid"]}' + (f' && {ready}' if ready else '')
        wr = bus.get('cmd_write')
        L += [f'  if ({bus["rsp_valid"]}) {n}_head = {n}_head + 1;',
              f'  if ({fire}) begin']
        addr = bus['cmd_address']
        L.append(f'    {n}_q_addr[{n}_tail % 16] = {addr}; {n}_q_err[{n}_tail % 16] = !inram({addr});')
        # Read data at acceptance, like the project adapters' bus models.
        L.append(f'    {n}_q_data[{n}_tail % 16] = inram({addr}) ? mem[{word(addr)}] : 0;')
        L.append(f'    {n}_q_taint[{n}_tail % 16] = inram({addr}) ? taint[{word(addr)}] : 0;')
        L.append(f'    {n}_q_due[{n}_tail % 16] = cycle + {int(bus.get("latency", 1))};')
        L.append(f'    {n}_q_id[{n}_tail % 16] = ' + (bus['cmd_id'] if bus.get('cmd_id') else '0') + ';')
        L.append(f'    {n}_q_rsp[{n}_tail % 16] = ' + (f'!{wr} || 1\'b{int(bool(bus.get("write_response", True)))}' if wr else '1') + ';')
        L.append(f'    {n}_tail = {n}_tail + 1;')
        L.append(f'    $fdisplay(fd, "B %0d {n} %h %0d", cycle, {addr}, ' + (wr if wr else "1'b0") + ');')
        if wr:
            data = bus.get('cmd_data')
            if bus.get('cmd_mask'):
                mask = bus['cmd_mask']
            else:
                size = bus['cmd_size']
                mask = f"((({size}) == 0 ? 4'b0001 : ({size}) == 1 ? 4'b0011 : 4'b1111) << ({addr}[1:0]))"
            L += [f'    if ({wr} && inram({addr})) begin',
                  f'      for (int i = 0; i < 4; i++) if ({mask}[i]) begin',
                  f'        mem[{word(addr)}][i*8 +: 8] = {data}[i*8 +: 8];']
            if ift:
                L.append(f'        taint[{word(addr)}][i*8 +: 8] = {data}__t[i*8 +: 8];')
            L += ['      end', '    end',
                  f'    if ({wr} && {addr} == tohost && done_at < 0) begin tohost_value = {data}; done_at = cycle; end']
        L.append('  end')
    r = binding['retire']
    if r['kind'] == 'rvfi':
        p = r.get('prefix', 'rvfi_')
        s = {k: p+k for k in RVFI}
        L += [f'  if ({s["valid"]}) $fdisplay(fd, "R %0d %h %h %h %0d %0d %h %h %h %0d %0d %h %h", cycle,',
              f'    {s["pc_rdata"]}, {s["pc_wdata"]}, {s["insn"]}, {s["trap"]}, {s["mode"]}, {s["rd_addr"]}, {s["rd_wdata"]},',
              f'    {s["mem_addr"]}, {s["mem_rmask"]}, {s["mem_wmask"]}, {s["mem_wdata"]}, {s["mem_rdata"]});']
    elif not ift:
        # Internal commit signals do not survive the gate-level shadow netlist.
        L.append(f'  if (dut.{r["valid"]}) $fdisplay(fd, "C %0d %h", cycle, dut.{r["pc"]});')
    t = binding.get('trap')
    if t:
        L.append(f'  if ({t["valid"]}) $fdisplay(fd, "T %0d %h %h", cycle, {t["cause"]}, {t["tval"]});')
        if t.get('privilege') and not ift:
            L.append(f'  if (dut.{t["privilege"]} != last_priv) begin $fdisplay(fd, "P %0d %0d", cycle, dut.{t["privilege"]}); last_priv = dut.{t["privilege"]}; end')
    if ift:
        for i, (sink, when) in enumerate(ift[1]):
            cond = f'(|{sink}__t)' + (f' && ({when} || (|{when}__t))' if when else '')
            L.append(f'  if ({cond}) $fdisplay(fd, "S %0d {i}", cycle);')
    L += ['end']
    L += ['initial begin',
          '  if (!$value$plusargs("mem=%s", path)) $fatal(1, "no +mem");', '  $readmemh(path, mem);',
          f'  for (int i = 0; i < {words}; i++) taint[i] = 0;',
          '  if ($value$plusargs("taint=%s", path)) $readmemh(path, taint);',
          '  if (!$value$plusargs("tohost=%h", tohost)) $fatal(1, "no +tohost");',
          '  if (!$value$plusargs("max=%d", max_cycles)) max_cycles = 100000;',
          '  if (!$value$plusargs("log=%s", path)) $fatal(1, "no +log");',
          '  fd = $fopen(path, "w");',
          f'  {reset} = 1;',
          f'  repeat ({int(binding.get("reset_cycles", 4))}) begin drive; #5 {clock} = 1; #5 {clock} = 0; end',
          f'  {reset} = 0;',
          '  while (cycle < max_cycles && (done_at < 0 || cycle < done_at + 8)) begin',
          f'    drive; #5 {clock} = 1; #5 {clock} = 0; cycle = cycle + 1;',
          '  end',
          '  $fdisplay(fd, "E %0d %0d %h", cycle, done_at, tohost_value);', '  $fclose(fd);', '  $finish;',
          'end', 'endmodule', '']
    return '\n'.join(L)


def build(binding, work, ift=None, shadow_text=None):
    """Compile once per RTL, testbench and tool identity. Returns the executable path."""
    Path(work).mkdir(parents=True, exist_ok=True)
    widths = ift[2] if ift else ports(binding)
    tb = testbench(binding, widths, ift and ift[:2])
    sources = shadow_text if shadow_text is not None else ''.join(p.read_text() for p in binding['rtl'])
    key = hashlib.sha256((sources+tb+native(['verilator', '--version'], work)).encode()).hexdigest()[:20]
    folder = Path(work)/f'build-{key}'
    exe = folder/'obj_dir/Vrvw_sec_tb'
    if exe.exists():
        return exe
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'tb.sv').write_text(tb)
    files = []
    if shadow_text is not None:
        (folder/'shadow.v').write_text(shadow_text); files = ['shadow.v']
    else:
        files = [str(p) for p in binding['rtl']]
    native(['verilator', '--binary', '--timing', '-j', '4', '-Wno-fatal', '-Wno-lint', '-Wno-style',
            '--top-module', 'rvw_sec_tb', '-O1', *files, 'tb.sv'], folder, timeout=1800)
    return exe


def simulate(binding, exe, elf, out, taint_words=None, max_cycles=None):
    """Run one ELF. Returns parsed retirements, bus events, traps, sinks and completion."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    mem, tohost, entry = image(elf, binding['ram_base'], binding['ram_size'])
    (out/'mem.hex').write_text(hexwords(mem))
    args = [str(exe), f'+mem={out/"mem.hex"}', f'+tohost={tohost:x}',
            f'+max={max_cycles or binding.get("max_cycles", 100000)}', f'+log={out/"sim.log"}']
    if taint_words:
        words = [0]*(binding['ram_size']//4)
        for index, mask in taint_words.items():
            words[index] = mask
        (out/'taint.hex').write_text('\n'.join(f'{w:08x}' for w in words)+'\n')
        args.append(f'+taint={out/"taint.hex"}')
    native(args, out, timeout=600)
    result = parse((out/'sim.log').read_text(), mem, binding)
    result['tohost_address'] = tohost
    result['image'] = bytes(mem)
    return result


def parse(text, mem, binding):
    result = dict(retired=[], bus=[], traps=[], sinks=[], privilege=[], cycles=None, done=None, tohost=None)
    for line in text.splitlines():
        w = line.split()
        if not w:
            continue
        if w[0] == 'R':
            keys = ('pc', 'pc_next', 'insn', 'trap', 'mode', 'rd', 'rd_wdata', 'mem_addr', 'mem_rmask',
                    'mem_wmask', 'mem_wdata', 'mem_rdata')
            vals = [int(x, 16) for x in w[2:5]] + [int(w[5]), int(w[6]), int(w[7], 16)] + [int(x, 16) for x in w[8:10]] + \
                   [int(w[10]), int(w[11])] + [int(x, 16) for x in w[12:14]]
            result['retired'].append(dict(cycle=int(w[1]), **dict(zip(keys, vals))))
        elif w[0] == 'C':
            pc = int(w[2], 16); off = pc-binding['ram_base']
            insn = int.from_bytes(mem[off:off+4], 'little') if 0 <= off < len(mem)-3 else 0
            result['retired'].append(dict(cycle=int(w[1]), pc=pc, insn=insn))
        elif w[0] == 'B':
            result['bus'].append(dict(cycle=int(w[1]), bus=w[2], address=int(w[3], 16), write=bool(int(w[4]))))
        elif w[0] == 'T':
            result['traps'].append(dict(cycle=int(w[1]), cause=int(w[2], 16), tval=int(w[3], 16)))
        elif w[0] == 'P':
            result['privilege'].append((int(w[1]), int(w[2])))
        elif w[0] == 'S':
            result['sinks'].append(dict(cycle=int(w[1]), sink=int(w[2])))
        elif w[0] == 'E':
            result['cycles'] = int(w[1]); result['done'] = int(w[2]); result['tohost'] = int(w[3], 16)
    return result


def cut(result):
    """Retirements up to and including the first tohost store."""
    rows = result['retired']
    for i, r in enumerate(rows):
        if 'mem_wmask' in r:
            if r['mem_wmask'] and r['mem_addr'] == result.get('tohost_address'):
                return rows[:i+1]
        elif result['done'] is not None and result['done'] >= 0 and r['cycle'] >= result['done'] and r['insn'] & 127 == 0x23:
            return rows[:i+1]
    return rows


def mode_at(result, cycle, default):
    """Privilege sampled at a cycle, from the declared privilege signal when present."""
    mode = 3 if result['privilege'] else default
    for c, m in result['privilege']:
        if c <= cycle:
            mode = m
    return mode


def c2(result, path, elf, binding, isa):
    """Write a C2 trace. RVFI fields are normalized to the Spike convention for unused fields."""
    rows = [json.dumps(dict(schema='rvw.rvfi/1', xlen=32, isa=isa, core=binding.get('name', binding['top']),
                            config='sec', elf=str(elf)))]
    traps = list(result['traps'])
    order = 0
    previous = None
    mem = result.get('image', b'')
    for r in cut(result):
        while traps and traps[0]['cycle'] < r['cycle']:
            t = traps.pop(0)
            if previous is not None and not t['cause'] >> 31 and 'pc_next' in previous:
                # RVFI here omits the trapped instruction. In order, it is the next PC.
                pc = previous['pc_next']; off = pc-binding['ram_base']
                insn = int.from_bytes(mem[off:off+4], 'little') if 0 <= off < len(mem)-3 else 0
                rows.append(json.dumps(dict(pc=hex(pc), pc_next=hex(r['pc']), insn=hex(insn), rd_wdata='0x0',
                                            mem_addr='0x0', mem_rdata='0x0', mem_wdata='0x0', rs1=0, rs2=0,
                                            rs1_rdata='0x0', rs2_rdata='0x0', order=order, cycle=t['cycle'],
                                            mode=mode_at(result, t['cycle']-1, previous.get('mode', 3)), rd=0, mem_rmask=0, mem_wmask=0, trap=True,
                                            intr=False, halt=False, mem_fault=False)))
                order += 1
            rows.append(json.dumps(dict(event='trap', cycle=t['cycle'], cause=hex(t['cause']),
                                        tval=hex(t['tval']), intr=bool(t['cause'] >> 31))))
        previous = r
        rd = r.get('rd', 0)
        access = r.get('mem_rmask', 0) or r.get('mem_wmask', 0)
        rec = dict(pc=hex(r['pc']), pc_next=hex(r.get('pc_next', 0)), insn=hex(r['insn']),
                   rd_wdata=hex(r.get('rd_wdata', 0) if rd else 0),
                   mem_addr=hex(r.get('mem_addr', 0) if access else 0),
                   mem_rdata=hex(r.get('mem_rdata', 0) if r.get('mem_rmask') else 0),
                   mem_wdata=hex(r.get('mem_wdata', 0) if r.get('mem_wmask') else 0),
                   rs1=0, rs2=0, rs1_rdata='0x0', rs2_rdata='0x0', order=order, cycle=r['cycle'],
                   mode=r.get('mode', 3), rd=rd, mem_rmask=r.get('mem_rmask', 0), mem_wmask=r.get('mem_wmask', 0),
                   trap=bool(r.get('trap', 0)), intr=False, halt=False, mem_fault=False)
        rows.append(json.dumps(rec)); order += 1
    status = 'pass' if result['tohost'] == 1 else 'fail' if result['done'] is not None and result['done'] >= 0 else 'timeout'
    rows.append(json.dumps(dict(event='end', cycle=max([r['cycle'] for r in result['retired']] or [0]), status=status)))
    Path(path).write_text('\n'.join(rows)+'\n')
    return status
