#!/usr/bin/env python3
"""Import a pinned external UDB checkout. Requires PyYAML 6.0.3 only at import time."""
import hashlib
import json
import sys
from pathlib import Path
import yaml

REVISION = '176fc36018be56925061566447a656b93eba0ddb'


def build(root):
    root = Path(root)
    registers = {}
    for path in sorted((root/'spec/std/isa/csr').rglob('*.yaml')):
        raw = path.read_bytes()
        row = yaml.safe_load(raw)
        name = row['name']
        if name in registers:
            raise ValueError(f'duplicate CSR {name}')
        registers[name] = dict(definition=row, source=str(path.relative_to(root)),
                               sha256=hashlib.sha256(raw).hexdigest(),
                               notices=[line for line in raw.decode().splitlines()
                                        if 'Copyright' in line or 'SPDX-License-Identifier:' in line])
    return dict(schema='rvw.csr-catalog/1', upstream='https://github.com/riscv/riscv-unified-db',
                revision=REVISION, registers=registers,
                limits=['Definitions preserve upstream expressions as data. No IDL interpreter runs.',
                        'This source revision does not define every allocated CSR.'])


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(json.dumps(build(sys.argv[1]), indent=2, ensure_ascii=False)+'\n')
