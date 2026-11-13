"""Run the available ISA kit and retain the scope of each result."""
import json
import math
import re
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
                         evidence='bounded/results.json', instruction_activation=test.get('instruction_activation')))
    return rows



def missing_checks(cfg):
    """Keep unselected ISA instructions and retirement channels visible."""
    if not cfg or 'root' not in cfg: return []
    file=Path(cfg['root'])/'insns'/('isa_'+cfg['isa']+'.txt')
    if not file.is_file():
        return [dict(check='isa_inventory',status='unsupported',reason='The ISA instruction list is unavailable.')]
    names={line.strip() for line in file.read_text().splitlines()
           if re.fullmatch(r'[a-z0-9_]+',line.strip())}
    names.update(cfg.get('instruction_models',{}))
    required={'cover'}
    for channel in range(cfg['nret']):
        required.update(f'insn_{name}_ch{channel}' for name in names)
        required.update(f'{kind}_ch{channel}' for kind in ('reg','pc_fwd','pc_bwd','liveness','unique','causal'))
    return [dict(check=name,status='unsupported',reason='Check is not selected in the project.')
            for name in sorted(required-set(cfg['checks']))]


def run(cfg, out, timeout, core_name, *, unbounded=False, engines=('abc:pdr',), machine=None, abstraction=None):
    from .riscv import run as bounded
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    if abstraction and not cfg:
        raise ValueError('abstraction requires a riscv_formal project')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    if cfg:
        bounded(cfg, out / 'bounded', timeout, core_name)
        from .isa_activation import run as activation
        activation(cfg, out / 'bounded', timeout)
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
    rows.extend(missing_checks(cfg))
    if cfg and abstraction:
        from .riscv_abstract import run as abstract
        proof_cfg = dict(cfg)
        proof_cfg['checks'] = [c for c in cfg['checks'] if c.startswith('insn_')] + ['cover']
        proof_cfg['check_options'] = {k:v for k,v in cfg.get('check_options',{}).items() if k in proof_cfg['checks']}
        plan = json.loads(Path(abstraction).read_text())
        result = abstract(proof_cfg, plan, out / 'abstract', timeout=timeout, budget=2*timeout)
        for row in result['rows']:
            rows.append(dict(check=row['check'] + ':abstraction',
                             status='failed' if row['status']=='fail' else 'inconclusive',
                             conditional_native_proof=row.get('conditional_native_proof',False),
                             reason='Native proof closed for the declared abstraction; full pipeline signoff is incomplete.'
                             if row.get('conditional_native_proof') else 'The conditional abstraction did not close.',
                             evidence='abstract/result.json'))
    machine_rows = {}
    if machine:
        from .machine_checks import run as run_machine
        path = Path(machine).resolve()
        plan = json.loads(path.read_text())
        if plan.get('schema') == 'rvw.csr-slices/1':
            from .csr_slices import execute
            result = execute(plan, path.parent, out / 'machine', timeout)
            rows.extend(dict(r, check='csr_consistency:' + r['csr'],
                             evidence='machine/result.json') for r in result['rows'])
            machine_rows['csr_consistency'] = dict(check='csr_consistency',
                status='failed' if result['status'] == 'fail' else 'inconclusive',
                reason='Per-CSR inventory; local cuts require pipeline composition.',
                evidence='machine/result.json')
        else:
            result = run_machine(plan, path.parent, out / 'machine', timeout)
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
