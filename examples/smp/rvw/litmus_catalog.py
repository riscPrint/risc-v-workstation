#!/usr/bin/env python3
"""Exact scalar litmus subset of the pinned upstream tree.

No instruction rewriting is permitted. Unsupported cases have an explicit
reason. The six original hash-pinned cases keep their existing compiler.
"""
import hashlib
import io
import tarfile
import json
from pathlib import Path
import re
import subprocess

PIN = '08728edcd99c7e1819d2d4c6789df6d5299ccb69'
BASE = 0x81000000


def parse_text(text):
    text = re.sub(r'\(\*.*?\*\)', '', text, flags=re.S)
    match = re.search(r'\{([^{}]*)\}', text, re.S)
    if not match:
        raise ValueError('initial-state block required')
    tail = text[match.end():]
    condition = re.search(r'\b(?:exists|forall)\b', tail)
    if not condition:
        raise ValueError('final-state condition required')
    table = tail[:condition.start()].strip().removesuffix('~').strip()
    rows = [r.strip() for r in table.split(';') if r.strip()]
    heads = [h.strip() for h in rows.pop(0).split('|')]
    harts = len(heads)
    if not 2 <= harts <= 8 or heads != [f'P{i}' for i in range(harts)]:
        raise ValueError('two to eight simple hart columns required')
    instructions = [[] for _ in heads]
    variables = set()
    regs = [{} for _ in heads]
    for item in match[1].split(';'):
        item = item.strip()
        if not item:
            continue
        assignment = re.fullmatch(r'(\d+):x(\d+)\s*=\s*([A-Za-z]\w*|-?\d+|0x[0-9a-fA-F]+)', item)
        if assignment:
            h, r, value = assignment.groups()
            h, r = int(h), int(r)
            if h >= harts or not 1 <= r <= 29 or r in regs[h]:
                raise ValueError('unsupported initial register')
            if re.fullmatch(r'[A-Za-z]\w*', value):
                variables.add(value)
                regs[h][r] = value
            else:
                regs[h][r] = int(value, 0) if 'x' in value else int(value)
            continue
        memory = re.fullmatch(r'([A-Za-z]\w*)\s*=\s*(0|0x0+)', item)
        if not memory:
            raise ValueError('only zero memory initialization is supported')
        variables.add(memory[1])
    if len(variables) > 16:
        raise ValueError('too many shared locations')
    addresses = {name: BASE+i*64 for i, name in enumerate(sorted(variables))}
    for register in regs:
        for r, value in register.items():
            if isinstance(value, str):
                register[r] = addresses[value]
    reg = r'x(?:[0-9]|[12][0-9])'
    patterns = [rf'(?:lb|lbu|lh|lhu|lw|lwu|ld|sb|sh|sw|sd) {reg},-?\d+\({reg}\)',
                r'fence (?:r|w|rw),(?:r|w|rw)', r'fence\.tso',
                rf'(?:add|sub|xor|or|and|sll|srl|sra|slt|sltu) {reg},{reg},{reg}',
                rf'(?:addi|xori|ori|andi|slli|srli|srai) {reg},{reg},-?\d+',
                rf'(?:li|mv) {reg},(?:{reg}|-?\d+)',
                rf'(?:amo(?:add|swap|xor|or|and|min|max|minu|maxu)\.[wd]|lr\.[wd]|sc\.[wd])(?:\.aq|\.rl|\.aqrl)? {reg},(?:{reg},)?(?:0)?\({reg}\)']
    for row in rows:
        columns = row.split('|')
        if len(columns) != harts:
            raise ValueError('unequal hart columns')
        for h, cell in enumerate(columns):
            cell = re.sub(r'\s+', ' ', cell.strip())
            cell = re.sub(r'\s*,\s*', ',', cell)
            if not cell:
                continue
            if not any(re.fullmatch(pattern, cell) for pattern in patterns):
                raise ValueError('unsupported instruction: '+cell)
            instructions[h].append(cell)
    final = tail[condition.end():]
    # Memory-valued final projections need a separately timed final RAM sample.
    if re.search(r'(?<![:\w])(?:[A-Za-z]\w*|\[[^]]+\])\s*=', final):
        raise ValueError('memory final projection is unsupported')
    projection = sorted(set(re.findall(r'\b\d+:x\d+\b', final)))
    if not projection or any(int(k.split(':')[0]) >= harts or int(k.split('x')[1]) > 29 for k in projection):
        raise ValueError('unsupported final register projection')
    return dict(harts=harts, registers=regs, instructions=instructions,
                addresses=addresses, projection=projection)


def catalog(root):
    root = Path(root).resolve()
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('litmus source revision differs from pin')
    # The complete tracked source set and bytes must agree with the pin.
    archive = subprocess.check_output(['git', '-C', str(root), 'archive', PIN, 'tests/non-mixed-size'])
    rows = []
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        files = {member.name: tar.extractfile(member).read() for member in tar
                 if member.isfile() and member.name.endswith('.litmus')}
    for relative, pinned in sorted(files.items()):
        path = root/relative
        if path.read_bytes() != pinned:
            raise ValueError('litmus source bytes differ from pin: '+relative)
        row = dict(test=relative, sha256=hashlib.sha256(pinned).hexdigest())
        try:
            spec = parse_text(pinned.decode())
            row.update(status='applicable', harts=spec['harts'])
        except ValueError as exc:
            row.update(status='unsupported', reason=str(exc))
        rows.append(row)
    return rows


def build(test, out, gcc='riscv64-unknown-elf-gcc'):
    # catalog() verifies source pins before callers select a case.
    import runpy
    test = Path(test)
    spec = parse_text(test.read_text())
    sources = []
    for h in range(spec['harts']):
        lines = ['.option norvc', '.text', '.globl _start', '_start:']
        lines += [f'li x{r}, 0' for r in range(1, 30)]
        lines += [f'li x{r}, {v}' for r, v in sorted(spec['registers'][h].items())]
        lines += spec['instructions'][h]
        lines += ['la x30, tohost', 'li x31, 1', 'sd x31, 0(x30)', 'park: j park',
                  '.section .tohost,"aw",@progbits', '.balign 64', '.globl tohost', 'tohost: .dword 0',
                  '.section .shared,"aw",@nobits', '.zero 1024']
        sources.append('\n'.join(lines)+'\n')
    builder = runpy.run_path(str(Path(__file__).with_name('programs.py')))['build']
    result = builder(out, harts=spec['harts'], sources=sources, gcc=gcc)
    (Path(out)/'litmus.json').write_text(json.dumps(dict(test=test.name,
        test_sha256=hashlib.sha256(test.read_bytes()).hexdigest(), projection=spec['projection']), indent=2)+'\n')
    return result
