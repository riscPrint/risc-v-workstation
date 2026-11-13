"""Speculative-leakage self-tests for RV32 cores through the paired contract runner.

Each gadget is a program pair under the speculative-constant-time contract. The secret is
x7. Architectural code only does register arithmetic with it. A wrong-path load in the
gadget uses a secret-derived address. Equal architectural traces with different bus or
timing observations show a transient secret-dependent access. The template must define
`sec_probe` (2 KiB), `sec_slot` (one word) and `sec_public` (one word).
"""
import json
from pathlib import Path
from .common import publish
from .pairs import run as run_pairs

PREFIX = ['andi t0, x7, 0x7c0', 'la s1, sec_probe', 'add t0, s1, t0']
GADGETS = {
    # Forward taken branch: static and cold predictors fall through into the load.
    'v1': PREFIX + ['li a0, 64', 'li a1, 16', 'bgeu a0, a1, 1f', 'lw t1, 0(t0)', 'lw t2, 0(t1)', '1:', 'nop'],
    # Indirect jump: the fall-through path is the wrong path until the target resolves.
    'v2': PREFIX + ['la t2, 1f', 'jalr x0, 0(t2)', 'lw t1, 0(t0)', 'lw t2, 0(t1)', '1:', 'nop'],
    # Return: same, through ra.
    'rsb': PREFIX + ['la ra, 1f', 'ret', 'lw t1, 0(t0)', 'lw t2, 0(t1)', '1:', 'nop'],
    # Store bypass: the slot holds the secret pointer, then the public one. A stale load leaks.
    'v4': PREFIX + ['la t2, sec_slot', 'sw t0, 0(t2)', 'la t4, sec_public', 'sw t4, 0(t2)', 'lw t3, 0(t2)',
                    'lw t1, 0(t3)', 'nop'],
}


def run(adapter_command, out, secrets=None, observations=None, gadgets=None, minimize_runs=4, timeout=1800):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    secrets = secrets or [{'x7': 64}, {'x7': 1024}]
    observations = observations or ['cycles', 'retire_cycles', 'dbus_trace']
    names = gadgets or list(GADGETS)
    cases, findings, complete = [], [], True
    for name in names:
        if name not in GADGETS:
            raise ValueError(f'unknown gadget {name}; choose from {", ".join(GADGETS)}')
        manifest = dict(contract='speculative-constant-time', clauses=['pc', 'memory', 'branch'],
                        observations=observations, public={'reset': 'cold', 'gadget': name},
                        program=GADGETS[name], secrets=secrets, minimize_runs=minimize_runs, timeout=timeout,
                        adapter_command=adapter_command)
        path = out/f'{name}.json'; path.write_text(json.dumps(manifest, indent=2)+'\n')
        report = run_pairs(path, out/name)
        cases.append(dict(gadget=name, status=report['status'], channels=report['comparison'].get('channels', []),
                          errors=report.get('errors', [])))
        complete = complete and report['complete']
        findings += [dict(gadget=name, **f) for f in report['findings']]
    return publish(out, 'spec-suite', findings, complete, cases=cases, expected='no_leak_observed',
                   receiver='paired bus trace and retirement timing; no cache receiver')
