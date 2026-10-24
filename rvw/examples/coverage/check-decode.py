#!/usr/bin/env python3
"""Compare the coverage decoder with GNU objdump on real ELF instruction encodings."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from rvw.cov.functional import decode

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('elf', nargs='+', type=Path)
parser.add_argument('--objdump', default='riscv64-unknown-elf-objdump')
parser.add_argument('--xlen', type=int, choices=(32, 64), default=64)
parser.add_argument('--json', action='store_true')
parser.add_argument('--out', type=Path)
args = parser.parse_args()
seen, mismatches, inputs, skipped = set(), Counter(), {}, []
for path in args.elf:
    if path.read_bytes()[:4] != b'\x7fELF':
        skipped.append(str(path))
        continue
    inputs[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    text = subprocess.run([args.objdump, '-d', '-M', 'no-aliases', str(path)],
                          check=True, capture_output=True, text=True).stdout
    for line in text.splitlines():
        match = re.match(r'\s*[0-9a-f]+:\s+([0-9a-f]{4,8})\s+([\w.]+)', line)
        if not match:
            continue
        word, expected = int(match[1], 16), match[2]
        if expected.startswith('.') or expected in ('unimp', 'c.unimp'):
            continue
        seen.add(word)
        actual = decode(word, args.xlen)['mnemonic']
        if actual != expected:
            mismatches[(expected, actual)] += 1
result = {"schema": "rvw.coverage-decode-check/1", "kind": "static-ELF-disassembly-comparison",
          "elf_count": len(inputs), "unique_encodings": len(seen), "elf_sha256": inputs,
          "skipped_non_elf": skipped,
          "mismatches": [{"expected": e, "actual": a, "count": n} for (e, a), n in sorted(mismatches.items())],
          "note": "Mnemonic agreement on disassembled encodings, not executed instruction or hardware coverage."}
content = json.dumps(result, indent=2) + '\n'
if args.out:
    args.out.write_text(content)
print(content if args.json else f'{len(inputs)} ELFs, {len(seen)} unique encodings, {sum(mismatches.values())} mismatches')
raise SystemExit(bool(mismatches) or not inputs)
