"""Generated machine-transition checks with explicit project observations."""
import hashlib
import json
import math
import os
import re
from pathlib import Path
from rvw.common.proc import run_group

# Inputs are sampled at one retirement-aligned transition. The project must
# supply both states of that transition. No pipeline latency is inferred.
RULES = {
    'csr_consistency': (dict(event=1, address=12, op=3, operand=32, before=32, after=32, read_data=32, trap=1, mode=2), 'event && address == CSR_ADDRESS', '''wire_placeholder'''),
    'x0': (dict(retire=1, rs1=5, rs2=5, rd=5, rs1_data=32, rs2_data=32, rd_data=32),
           'retire', 'assert(rs1 != 0 || rs1_data == 0); assert(rs2 != 0 || rs2_data == 0); assert(rd != 0 || rd_data == 0);'),
    'flush_retirement': (dict(retire=1, retired_killed=1), 'retire', 'assert(!retired_killed);'),
    'exception_entry': (dict(event=1, pc=32, epc_after=32, cause=32, cause_after=32, vector=32, next_pc=32,
                            ie_before=1, pie_after=1, ie_after=1, mode_before=2, previous_mode_after=2),
                        'event', 'assert(epc_after == pc); assert(cause_after == cause); assert(next_pc == (vector & 32\'hfffffffc)); assert(!ie_after); assert(pie_after == ie_before); assert(previous_mode_after == mode_before);'),
    'interrupt_entry': (dict(event=1, pc=32, epc_after=32, cause=32, cause_after=32, vector=32, next_pc=32,
                            ie_before=1, pie_after=1, ie_after=1, mode_before=2, previous_mode_after=2),
                        'event', 'assert(epc_after == pc); assert(cause_after == (cause | 32\'h80000000)); assert(next_pc == ((vector & 32\'hfffffffc) + (vector[1:0] == 1 ? (cause << 2) : 0))); assert(!ie_after); assert(pie_after == ie_before); assert(previous_mode_after == mode_before);'),
    'trap_return': (dict(event=1, epc=32, next_pc=32, pie_before=1, ie_after=1, pie_after=1,
                        previous_mode_before=2, mode_after=2, previous_mode_after=2),
                    'event', 'assert(next_pc == epc); assert(ie_after == pie_before); assert(pie_after); assert(mode_after == previous_mode_before);'),
    'trap_pc_chain': (dict(retire=1, pc=32, next_pc=32, redirect=1, redirect_pc=32), 'retire',
                      'if(seen) assert(pc == (redirect ? redirect_pc : previous_pc));'),
    'instruction_memory': (dict(retire=1, pc=32, insn=32, fetch=1, fetch_addr=32, fetch_data=32),
                           'retire && pc == watched_addr', 'assert(insn == watched_data);'),
}


def monitor(check, selection=None):
    widths, trigger, body = RULES[check]
    text = ['module rvw_machine_check(input clock, reset,' + ','.join(
        f'input [{w-1}:0] {n}' for n,w in widths.items()) + ');']
    if check == 'trap_return':
        least = (selection or {}).get('least_privileged_mode', 0)
        if type(least) is not int or least not in (0, 3):
            raise ValueError('least_privileged_mode must be 0 or 3')
        body += f' assert(previous_mode_after == 2\'d{least});'
    if check == 'trap_pc_chain':
        text += ['reg seen = 0; reg [31:0] previous_pc;',
                 'always @(posedge clock) if(reset) seen <= 0; else if(retire) begin seen <= 1; previous_pc <= next_pc; end']
    if check == 'instruction_memory':
        text += ['(* anyconst *) reg [31:0] watched_addr;', '(* anyconst *) reg [31:0] watched_data;',
                 'always @(posedge clock) if(!reset && fetch && fetch_addr == watched_addr) assume(fetch_data == watched_data);']
    if check == 'csr_consistency':
        from rvw.csr.catalog import catalog
        definition = catalog()['registers'][selection['csr']]['definition']
        mask = selection['write_mask']
        if type(mask) is not int or not 0 <= mask < 2**32:
            raise ValueError('declare a 32-bit CSR write mask')
        address = definition['address']
        if not definition['writable'] and mask:
            raise ValueError('catalog read-only CSR cannot have writable bits')
        privilege = {'U':0, 'S':1, 'M':3}[definition['priv_mode']]
        trigger = trigger.replace('CSR_ADDRESS', str(address))
        text += [f'wire write_intent = op == 1 || ((op == 2 || op == 3) && operand != 0);',
                 f'wire denied = mode < {privilege} || (write_intent && {int(not definition["writable"])});',
                 'wire [31:0] value = op == 2 ? before | operand : op == 3 ? before & ~operand : operand;',
                 f"wire [31:0] expected = (before & ~32'd{mask}) | (value & 32'd{mask});"]
        body = 'assert(op >= 1 && op <= 3); assert(trap == denied); if(!denied) begin assert(read_data == before); assert(after == (write_intent ? expected : before)); end else assert(after == before);'
    text += [f'always @(posedge clock) if(!reset && ({trigger})) begin', body,
             'cover(1);', 'end', 'endmodule']
    return '\n'.join(text) + '\n'


def generate(plan, root, out):
    if plan.get('schema') != 'rvw.machine-checks/1' or plan.get('xlen') != 32:
        raise ValueError('expected rvw.machine-checks/1 with XLEN 32')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = []
    for i, path in enumerate(plan['sources']):
        data = (Path(root)/os.path.expandvars(path)).read_text()
        sources.append((f'input{i}.sv', data))
    rows = []
    for check, selection in plan['checks'].items():
        if check not in RULES:
            raise ValueError('unsupported machine rule: ' + check)
        if 'unsupported' in selection:
            rows.append(dict(check=check, status='unsupported', reason=selection['unsupported']))
            continue
        if 'not_applicable' in selection:
            if not selection['not_applicable']:
                raise ValueError('not applicable needs a reason')
            rows.append(dict(check=check, status='not applicable', reason=selection['not_applicable']))
            continue
        signals = selection['signals']
        if set(signals) != set(RULES[check][0]):
            raise ValueError('map every input for ' + check)
        for name in [plan['top'], plan['clock'], plan['reset'], *signals.values()]:
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', name):
                raise ValueError('machine bindings require local RTL identifiers')
        directory = out/check; directory.mkdir()
        instance = 'rvw_machine_check rvw_check(.clock(' + plan['clock'] + '),.reset(' + plan['reset'] + '),' + ','.join(f'.{k}({v})' for k,v in signals.items()) + ');'
        # Instrument a captured source copy, never the external checkout.
        injected = 0
        for filename, data in sources:
            pattern = r'(\bmodule\s+' + re.escape(plan['top']) + r'\b[\s\S]*?)(\bendmodule\b)'
            data, count = re.subn(pattern, lambda m: m[1] + '\n' + instance + '\nalways @* assume(' + plan['reset'] + ' == $initstate);\n' + m[2], data)
            injected += count
            (directory/filename).write_text(data)
        if injected != 1:
            raise ValueError('top must occur exactly once')
        (directory/'monitor.sv').write_text(monitor(check, selection))
        names = [n for n,_ in sources] + ['monitor.sv']
        depth = plan.get('depth',20)
        if type(depth) is not int or not 2 <= depth <= 200:
            raise ValueError('depth must be 2..200')
        engine = selection.get('engine', 'abc bmc3')
        if engine not in ('abc bmc3', 'smtbmc bitwuzla', 'smtbmc yices'):
            raise ValueError('unsupported machine engine')
        cuts = selection.get('cone_cuts', [])
        if not isinstance(cuts, list) or len(cuts) != len(set(cuts)) or any(
                not isinstance(c, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', c) for c in cuts):
            raise ValueError('cone cuts must be unique local RTL identifiers')
        cut_script = ''.join('select -assert-count 1 ' + plan['top'] + '/w:' + c + '\ncutpoint ' + plan['top'] + '/w:' + c + '\n' for c in cuts)
        (directory/'check.sby').write_text('[tasks]\ncheck\ncover\n[options]\ncheck: mode bmc\ncover: mode cover\ndepth ' + str(depth) + '\n[engines]\ncheck: ' + engine + '\ncover: smtbmc bitwuzla\n[script]\nread -formal -sv -noautowire ' + ' '.join(names) + '\nprep -top ' + plan['top'] + '\n' + cut_script + 'opt_clean\n[files]\n' + '\n'.join(names) + '\n')
        rows.append(dict(check=check,status='generated',depth=depth,evidence=f'{check}/check.sby', scope='local cone contract' if cuts else 'pipeline', cone_cuts=cuts))
    report = dict(schema='rvw.machine-check-results/1',status='generated',rows=rows,
                  source_sha256={str(p):hashlib.sha256(d.encode()).hexdigest() for p,d in sources},
                  limits=['RV32 transition slices; not a complete privileged ISA model.',
                          'Project owns event alignment and killed-instruction tracking.',
                          'Instruction memory assumes immutable 32-bit words at observed fetches; compressed and self-modifying code need another model.',
                          'Reset is asserted only in the initial state.'])
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(plan, root, out, timeout):
    import time
    from .runtime import load_average, timeout_details
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    report = generate(plan, root, out)
    for row in report['rows']:
        if row['status'] != 'generated': continue
        tokens = {}
        row['native_attempts'] = []
        for task in ('check','cover'):
            directory = Path(out)/row['check']
            began = time.monotonic()
            load_start = load_average()
            with (directory/(task+'.log')).open('w') as log:
                result = run_group(['sby','-f','check.sby',task],cwd=directory,stdout=log,stderr=log,timeout=timeout)
            attempt = dict(task=task, wall_s=time.monotonic()-began, timeout_s=timeout,
                           load_average_start=load_start, load_average_end=load_average(),
                           status='timeout' if result.timed_out else 'completed')
            if result.timed_out:
                attempt.update(timeout_details(attempt['wall_s'],timeout,load_start))
            row['native_attempts'].append(attempt)
            status = directory/('check_'+task)/'status'
            tokens[task] = status.read_text().split()[0] if status.is_file() and result.returncode == 0 and not result.timed_out else 'INCOMPLETE'
            if status.is_file() and status.read_text().split()[0] == 'FAIL' and task == 'check': tokens[task] = 'FAIL'
        warnings = '\n'.join(p.read_text(errors='replace') for p in (Path(out)/row['check']).rglob('*.log'))
        if 'Resizing cell port' in warnings or 'implicitly declared' in warnings:
            tokens['check'] = 'INVALID_BINDING'
        row['status'] = 'failed' if tokens['check'] == 'FAIL' else 'bounded' if all(t == 'PASS' for t in tokens.values()) else 'inconclusive'
        row['native'] = tokens
        if row.get('cone_cuts') and row['status'] == 'bounded':
            row['local_status'] = 'bounded'
            row['status'] = 'inconclusive'
            row['reason'] = 'Local cone contract passed; pipeline composition is not established.'
    report['status'] = 'fail' if any(r['status']=='failed' for r in report['rows']) else 'inconclusive'
    (Path(out)/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
