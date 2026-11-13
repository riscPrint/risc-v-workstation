"""Test helper: turn a Spike `-l --log-commits` log into a C2 trace (no CSR or memory fields)."""
import json
import re

CAUSES = {'trap_instruction_address_misaligned': 0, 'trap_illegal_instruction': 2, 'trap_breakpoint': 3,
          'trap_user_ecall': 8, 'trap_supervisor_ecall': 9, 'trap_machine_ecall': 11}
FETCH = re.compile(r'^core\s+0: 0x([0-9a-f]+) \(0x([0-9a-f]+)\)')
COMMIT = re.compile(r'^core\s+0: (\d) 0x([0-9a-f]+) \(0x([0-9a-f]+)\)')
EXCEPTION = re.compile(r'^core\s+0: exception (\w+), epc 0x([0-9a-f]+)')
INTERRUPT = re.compile(r'^core\s+0: interrupt #(\d+), epc 0x([0-9a-f]+)')


def convert(log_text, path, *, low=0x80000000, xlen=64, stop=None):
    """stop: cut the trace after the first retirement at this pc (an idle loop)."""
    rows, events, fetched, mode = [], [], None, 3
    for line in log_text.splitlines():
        if (m := COMMIT.match(line)):
            mode = int(m.group(1))
            pc, insn = int(m.group(2), 16), int(m.group(3), 16)
            if pc >= low:
                rows.append(dict(pc=pc, insn=insn, mode=mode, trap=False))
                if stop is not None and pc == stop:
                    rows.append(dict(pc=pc, insn=insn, mode=mode, trap=False))   # successor for pc_next
                    break
            fetched = None
        elif (m := EXCEPTION.match(line)):
            if fetched and fetched[0] >= low:
                rows.append(dict(pc=fetched[0], insn=fetched[1], mode=mode, trap=True,
                                 cause=CAUSES[m.group(1)]))
            mode = 3
        elif (m := INTERRUPT.match(line)):
            rows.append(dict(irq=int(m.group(1))))
            mode = 3
        elif (m := FETCH.match(line)):
            fetched = (int(m.group(1), 16), int(m.group(2), 16))
    records = [dict(schema='rvw.rvfi/1', xlen=xlen, isa='rv64imac', core='spike', config='log', elf='fixture')]
    real = [r for r in rows if 'pc' in r]
    order, pending = 0, None
    for index, row in enumerate(rows):
        if 'irq' in row:
            pending = row['irq']
            continue
        nxt = next((r for r in rows[index + 1:] if 'pc' in r), None)
        if nxt is None:
            break
        if pending is not None:
            records.append(dict(event='trap', cycle=order, cause=hex((1 << (xlen - 1)) | pending), tval='0x0', intr=True))
        record = {k: '0x0' for k in 'rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
        record.update(order=order, cycle=order, pc=hex(row['pc']), pc_next=hex(nxt['pc']), insn=hex(row['insn']),
                      mode=row['mode'], trap=row['trap'], intr=pending is not None or bool(index and rows[index - 1].get('trap')),
                      halt=False, rs1=0, rs2=0, rd=0, mem_rmask=0, mem_wmask=0, mem_fault=False)
        pending = None
        records.append(record)
        if row['trap']:
            records.append(dict(event='trap', cycle=order, cause=hex(row['cause']), tval='0x0', intr=False))
        order += 1
    records.append(dict(event='end', cycle=order, status='pass'))
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    return len(real)


def spike_log(elf, *, lines=600, isa='rv64imac', memory='-m0x7ffff000:0x1001000'):
    """First `lines` log lines of a Spike run with commits (Spike runs until it is stopped)."""
    import subprocess
    process = subprocess.Popen(['spike', f'--isa={isa}', '-l', '--log-commits', memory, str(elf)],
                               stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    out = []
    try:
        for line in process.stderr:
            out.append(line)
            if len(out) >= lines:
                break
    finally:
        process.kill()
        process.wait(10)
    return ''.join(out)


def symbol(elf, name, nm='/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-nm'):
    import subprocess
    for line in subprocess.run([nm, str(elf)], capture_output=True, text=True, check=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == name:
            return int(parts[0], 16)
    raise KeyError(name)
