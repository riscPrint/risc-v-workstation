#!/usr/bin/env python3
"""Prepare named properties on an existing BOOM export. Never edit the core."""
import argparse
import hashlib
import json
from pathlib import Path
import re

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--verilog', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
a = p.parse_args()
raw = a.verilog.read_bytes()
text = raw.decode()
match = re.search(r'^module RenameFreeList \(.*?^endmodule', text, re.M | re.S)
if not match:
    raise SystemExit('RenameFreeList is not present in this export')
body = match.group()
ports = re.findall(r'^\s*(input|output)\s+wire\s*(?:\[(\d+):0\])?\s+(\w+)\s*[,\n]', body, re.M)
widths = {name: int(msb)+1 if msb else 1 for _, msb, name in ports}
if not {'clk', 'reset', 'io_alloc_pregs_0_valid', 'io_alloc_pregs_0_payload', 'io_debug_freelist'} <= widths.keys():
    raise SystemExit('unsupported export ports')
a.out.mkdir(parents=True, exist_ok=False)
# Check only the named properties. Native assertion environment requirements need a separate harness.
(a.out / 'freelist.v').write_text('`define SYNTHESIS\n' + body + '\n`undef SYNTHESIS\n')
inputs = [n for d, _, n in ports if d == 'input' and n not in ('clk', 'reset')]
outputs = [n for d, _, n in ports if d == 'output']
plan = {'verilog': ['freelist.v'], 'signals': {n: w for n, w in widths.items() if n not in ('clk', 'reset')},
        'predicates': {'allocation_range': '!io_alloc_pregs_0_valid || (io_alloc_pregs_0_payload < 52)',
                       'allocation_in_debug_set': '!io_alloc_pregs_0_valid || ((io_debug_freelist >> io_alloc_pregs_0_payload) & 1)'},
        'components': [{'id': 'freelist', 'top': 'RenameFreeList', 'inputs': inputs, 'outputs': outputs,
                        'assumes': [], 'guarantees': ['allocation_range', 'allocation_in_debug_set']}],
        'export_sha256': hashlib.sha256(raw).hexdigest(),
        'scope': 'Existing export; generator revision is not certified. No native assertion or whole-core claim.'}
(a.out / 'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
print(a.out / 'plan.json')
