#!/usr/bin/env python3
"""Build scalar FP class programs with result bits and flags supplied by Spike."""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

from rvw.common.riscv import decode
from rvw.cosim.elf import Elf
from rvw.cov.fp import encodings, format_width
from programs import VALUES, envelope


def cases(xlen, width, seed, random_cases):
    isa = f'rv{xlen}imaf' + ('d' if xlen == 64 else '') + 'c_zicsr_zifencei'
    rng = random.Random(seed)
    result = {}
    for name, original in sorted(encodings(xlen, isa).items()):
        if format_width(name) != width:
            continue
        d = decode(original, xlen)
        word = original
        if d.length == 4:
            word = (word & ~(31 << 7)) | ((0 if d.dest_bank == 'f' or d.cls == 'store' else 28) << 7)
            for pos, reg in enumerate((d.rs1, d.rs2, d.rs3), 1):
                if reg is not None:
                    bank, _ = reg
                    index = pos if bank == 'f' else (10 if d.cls in ('load', 'store') else 6)
                    shift = {1: 15, 2: 20, 3: 27}[pos]
                    word = (word & ~(31 << shift)) | (index << shift)
        source_width = 64 if name == 'fcvt.s.d' else 32 if name == 'fcvt.d.s' else width
        values = VALUES[source_width]
        patterns = [(a, values[(i+1) % 6], values[(i+2) % 6]) for i, a in enumerate(values)]
        patterns += [(rng.getrandbits(source_width), rng.getrandbits(source_width), rng.getrandbits(source_width))
                     for _ in range(random_cases)]
        entries = []
        rounded = name.startswith(('fadd', 'fsub', 'fmul', 'fdiv', 'fsqrt', 'fmadd', 'fmsub', 'fnmadd', 'fnmsub', 'fcvt'))
        for operands in patterns:
            for rm in range(5):
                encoded = ((word & ~(7 << 12)) | (rm << 12)) if rounded else word
                entries.append(dict(insn=encoded, rm=rm, operands=operands, source_width=source_width,
                                    name=name, width=width, xlen=xlen))
        result[name] = entries
    return result


def source(entries, expected=None):
    body, data = [], []
    for index, entry in enumerate(entries):
        width, sw = entry['width'], entry['source_width']
        d = decode(entry['insn'], entry['xlen'])
        datum = '.word' if sw == 32 else '.dword'
        load = 'flw' if sw == 32 else 'fld'
        # Distinct aligned input words also support compressed base and SP forms.
        data += ['.balign 8', f'input_{index}: {datum} 0x{entry["operands"][0]:x}', '.dword 0,0,0']
        for pos, value in enumerate(entry['operands'], 1):
            data += ['.balign 8', f'input_{index}_{pos}: {datum} 0x{value:x}']
            body += [f'  la t0, input_{index}_{pos}', f'  {load} f{pos}, 0(t0)']
        body += [f'  {load} f9, 0(t0)', f'  la a0, input_{index}', '  mv s1, a0', '  mv sp, a0',
                 f'  li t1, 0x{entry["operands"][0] & ((1 << entry["xlen"]) - 1):x}',
                 f'  li t0, {entry["rm"] << 5}', '  csrw fcsr, t0',
                 f'.globl fp_case_{index}', f'fp_case_{index}:',
                 f'  {".2byte" if d.length == 2 else ".word"} 0x{entry["insn"]:x}']
        if expected is not None:
            value = expected[index]
            body += ['  frflags t2', f'  li t0, {value["flags"]}', '  bne t2, t0, fail']
            if d.cls == 'store':
                # The encoded compressed offsets are retained. Compare the exact written bytes.
                body += [f'  la t0, input_{index}',
                         f'  {"lw" if width == 32 else "ld"} t3, {value["offset"]}(t0)']
            elif d.dest_bank == 'f':
                body += [f'  fmv.x.{"w" if width == 32 else "d"} t3, f{value["fd"]}']
            value_bits = value['value'] & ((1 << width) - 1) if d.dest_bank == 'f' or d.cls == 'store' else value['value']
            if width == 32 and (d.dest_bank == 'f' or d.cls == 'store') and entry['xlen'] == 64 and value_bits & (1 << 31):
                value_bits |= ((1 << 64) - 1) ^ ((1 << 32) - 1)
            body += [f'  li t0, 0x{value_bits:x}', '  bne t3, t0, fail']
    return envelope('\n'.join(body), '\n'.join(data))


def expectations(entries, symbols, rows):
    by_pc = {symbols[f'fp_case_{i}']: i for i in range(len(entries))}
    result = {}
    for row in rows:
        if 'event' in row:
            continue
        index = by_pc.get(int(row['pc'], 0))
        if index is None:
            continue
        entry = entries[index]
        if int(row['insn'], 0) != entry['insn'] or row['trap']:
            raise ValueError('Spike did not execute the planned FP instruction')
        d = decode(entry['insn'], entry['xlen'])
        key = 'mem_wdata' if d.cls == 'store' else 'fd_wdata' if d.dest_bank == 'f' else 'rd_wdata'
        if d.dest_bank == 'f' and not row['fd_valid']:
            raise ValueError('reference trace did not export the FP result')
        result[index] = dict(value=int(row[key], 0), flags=int(row['fflags'], 0),
                             fd=row['fd'], offset=int(row['mem_addr'], 0) - symbols[f'input_{index}'])
    if len(result) != len(entries):
        raise ValueError('reference trace does not contain every planned FP case')
    return [result[i] for i in range(len(entries))]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xlen', type=int, choices=(32, 64), required=True)
    p.add_argument('--width', type=int, choices=(32, 64), required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--random-cases', type=int, default=8)
    p.add_argument('--platform', type=Path, required=True)
    p.add_argument('--linker', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--compiler', default='riscv64-unknown-elf-gcc')
    args = p.parse_args()
    if args.width > args.xlen:
        p.error('RV32 profile has F only')
    args.out.mkdir(parents=True, exist_ok=True)
    oracle = args.out / 'oracle'
    oracle.mkdir(exist_ok=True)
    march = f'rv{args.xlen}imaf' + ('dc' if args.xlen == 64 else 'c') + '_zicsr_zifencei'
    abi = 'lp64d' if args.xlen == 64 else 'ilp32f'
    def compile(source_path, elf):
        subprocess.run([args.compiler, '-march='+march, '-mabi='+abi, '-nostdlib', '-nostartfiles',
                        '-T', str(args.linker), str(source_path), '-o', str(elf)], check=True)
    for name, entries in cases(args.xlen, args.width, args.seed, args.random_cases).items():
        stem = f'fp{args.width}-{name}'
        s, elf, trace = (oracle / (stem + ext) for ext in ('.S', '.elf', '.jsonl'))
        s.write_text(source(entries))
        compile(s, elf)
        run = subprocess.run([sys.executable, '-m', 'rvw', 'cosim', 'generate', '--elf', str(elf),
                              '--core', 'vexiiriscv', '--platform', str(args.platform), '--out', str(trace),
                              '--max-instructions', '100000', '--json'], check=True, capture_output=True, text=True)
        if json.loads(run.stdout)['termination'] != 'pass':
            raise ValueError('reference program did not pass')
        with trace.open() as stream:
            header = json.loads(next(stream))
            if header['schema'] != 'rvw.rvfi/2' or 'state' not in header['capabilities']:
                raise ValueError('reference generation requires C2/2 FP state')
            expected = expectations(entries, Elf(elf).symbols, (json.loads(line) for line in stream))
        final = args.out / (stem + '.S')
        final.write_text(source(entries, expected))
        compile(final, args.out / (stem + '.elf'))
        (oracle / (stem + '-plan.json')).write_text(json.dumps(dict(seed=args.seed, cases=entries,
             expected=expected, oracle_sha256=hashlib.sha256(elf.read_bytes()).hexdigest()), indent=2)+'\n')
        print(stem, len(entries), flush=True)


if __name__ == '__main__':
    main()
