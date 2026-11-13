"""Run the available ISA kit and retain the scope of each result."""
import json
import math
from pathlib import Path

MACHINE_CHECKS = ('exception_entry', 'interrupt_entry', 'trap_return', 'csr_consistency',
                  'instruction_memory', 'x0', 'flush_retirement', 'trap_pc_chain')


def bounded_rows(suite):
    rows = []
    for test in suite['tests']:
        status = test['status']
        depth = test.get('formal_settings', {}).get('cycles', [suite['bounded_depth']])[-1]
        why = test.get('inconclusive')
        outcome = ('failed' if status == 'fail' else 'bounded' if status == 'pass' and not why
                   else 'inconclusive')
        rows.append(dict(check=test['id'], status=outcome, depth=depth,
                         reason=why or ('' if outcome == 'bounded' else status),
                         evidence='bounded/results.json'))
    return rows


def run(cfg, out, timeout, core_name, *, unbounded=False, engines=('abc:pdr',), machine=None):
    from .riscv import run as bounded
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    if cfg:
        bounded(cfg, out / 'bounded', timeout, core_name)
        rows.extend(bounded_rows(json.loads((out / 'bounded/results.json').read_text())))
        if unbounded:
            from .riscv_proof import run as prove
            proof_cfg = dict(cfg)
            proof_cfg['checks'] = [c for c in cfg['checks'] if c.startswith('insn_')] + ['cover']
            proof_cfg['check_options'] = {k: v for k, v in cfg.get('check_options', {}).items()
                                          if k in proof_cfg['checks']}
            proof = prove(proof_cfg, out / 'unbounded', list(engines), timeout)
            for row in proof['rows']:
                # The portfolio owns assumption activation. Do not promote engine PASS.
                rows.append(dict(check=row['check'] + ':unbounded',
                                 status='proven' if row['status'] == 'pass' else
                                 'failed' if row['status'] == 'fail' else 'inconclusive',
                                 reason='See portfolio assumptions and activation limits.',
                                 evidence='unbounded/result.json'))
    else:
        rows.append(dict(check='instruction_checks', status='unsupported',
                         reason='Project has no riscv_formal section.'))
    machine_rows = {}
    if machine:
        from .machine_checks import run as run_machine
        path = Path(machine).resolve()
        result = run_machine(json.loads(path.read_text()), path.parent, out / 'machine', timeout)
        machine_rows = {r['check']: dict(r, evidence='machine/result.json') for r in result['rows']}
    for check in MACHINE_CHECKS:
        rows.append(machine_rows.get(check, dict(check=check, status='unsupported', reason='No machine-state binding selected.')))
    rows += [dict(check='sail_models', status='unsupported',
                  reason='Select generated models through riscv_formal.instruction_models.'),
             dict(check='adapter_conformance', status='unsupported',
                  reason='RVFI export or monitor equivalence is not certified by instruction checks.')]
    if cfg and cfg.get('instruction_models'):
        rows[-2] = dict(check='sail_models', status='not applicable',
                        reason='Selected instruction models are checked in the instruction rows; provenance is in bounded/results.json.')
    report = dict(schema='rvw.isa-signoff/1', core=core_name, rows=rows,
                  status='fail' if any(r['status'] == 'failed' for r in rows) else 'inconclusive',
                  limits=['Bounded results do not establish unbounded ISA conformance.',
                          'Unsupported rows are gaps, not passes.',
                          'Source assumptions and reachability remain part of each result.'])
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def table(report):
    lines = ['Check | Outcome | Reason', '--- | --- | ---']
    for row in report['rows']:
        outcome = f"bounded {row['depth']}" if row['status'] == 'bounded' else row['status']
        lines.append(f"{row['check']} | {outcome} | {row.get('reason', '')}")
    return '\n'.join(lines)
