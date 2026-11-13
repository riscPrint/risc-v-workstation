#!/usr/bin/env python3
"""Run each public fixture through the bounded external MCP runner."""
import argparse
import json
from pathlib import Path
import sys

from rvw.agent_bench.external import run_trial

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--budget-s', type=float, default=30)
parser.add_argument('--max-calls', type=int, default=32)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
print('| Task | Complete | Correct fix | False fix | Inconclusive preserved | Calls | Client seconds |')
print('|---|---|---|---|---|---:|---:|')
for name in ('tasks', 'misleading'):
    pack = Path(__file__).resolve().with_name(name + '.json')
    for task in json.loads(pack.read_text())['tasks']:
        result = run_trial(pack, task['id'], [sys.executable, '-m', 'rvw.agent_bench.external_client'],
                           args.out / task['id'], budget_s=args.budget_s, max_calls=args.max_calls,
                           model='scripted MCP baseline')
        score, attempt = result['summary'], result['attempts'][0]
        print(f"| {task['id']} | {attempt['complete']} | {score['correct_fixes']} | "
              f"{score['false_fixes']} | {score['inconclusive_preserved']} | {attempt['calls']} | "
              f"{attempt['wall_s']:.3f} |", flush=True)
