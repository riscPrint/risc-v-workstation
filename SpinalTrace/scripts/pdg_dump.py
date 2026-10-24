#!/usr/bin/env python3
"""Print a SpinalTrace/ChiselTrace pdg.json in a compact, human-readable form."""
import json, sys

d = json.load(open(sys.argv[1]))
for i, v in enumerate(d['vertices']):
    print(f"{i:3} {v['name']:<40} {v['kind']:<14} {'clk' if v['clocked'] else '   '} "
          f"{(v['assignsTo'] or '-'):<22} {v['file'].split('/')[-1]}:{v['line']} "
          f"{'U' if v['isChiselStatement'] else 'g'} cond={v['condition']} delay={v['assignDelay']} "
          f"range={v.get('assignRange')} rel={v['relatedSignal']}")
for e in d['edges']:
    if e['kind'] != 'Declaration':
        print(f"   {e['from']} -> {e['to']} {e['kind']} {'clk' if e['clocked'] else ''} {e['condition'] or ''}")
print('predicates:', [p['name'] for p in d['predicates']])
print('cfg:', json.dumps(d['cfg']))
print('meta:', json.dumps(d.get('spinaltrace')))
