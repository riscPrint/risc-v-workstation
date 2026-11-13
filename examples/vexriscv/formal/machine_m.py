"""Bind machine entry and return rules to the measured RV32IM export."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from rvw.formal.machine_checks import RULES, run

RTL_SHA256 = '420f2d5bd0100a07ca48542d232c76e8048a4bb73e03757e51cd1aa664027a37'


def prepare(rtl, out):
    raw = Path(rtl).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RTL_SHA256:
        raise ValueError('select the measured FormalMTop RTL; another export needs new bindings')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    entries = dict(pc='writeBack_PC', cause="{28'b0,CsrPlugin_trapCause}",
                   vector="{CsrPlugin_mtvec_base,CsrPlugin_mtvec_mode}",
                   next_pc='CsrPlugin_jumpInterface_payload', ie_before='CsrPlugin_mstatus_MIE',
                   mode_before='CsrPlugin_privilege')
    after = dict(epc_after='CsrPlugin_mepc', cause_after="{CsrPlugin_mcause_interrupt,27'b0,CsrPlugin_mcause_exceptionCode}",
                 pie_after='CsrPlugin_mstatus_MPIE', ie_after='CsrPlugin_mstatus_MIE',
                 previous_mode_after='CsrPlugin_mstatus_MPP')
    bindings = {
        'exception_entry': (dict(entries, event='CsrPlugin_hadException && when_CsrPlugin_l1398'), after),
        'interrupt_entry': (dict(entries, event='!CsrPlugin_hadException && CsrPlugin_interruptJump && when_CsrPlugin_l1398'), after),
        'trap_return': (dict(event="when_CsrPlugin_l1456 && switch_CsrPlugin_l1460 == 2'b11",
                            epc='CsrPlugin_mepc', next_pc='CsrPlugin_jumpInterface_payload',
                            pie_before='CsrPlugin_mstatus_MPIE', previous_mode_before='CsrPlugin_mstatus_MPP'),
                        dict(ie_after='CsrPlugin_mstatus_MIE', pie_after='CsrPlugin_mstatus_MPIE', mode_after='CsrPlugin_privilege', previous_mode_after='CsrPlugin_mstatus_MPP')),
    }
    observations, checks = [], {}
    for check, (before, current) in bindings.items():
        signals = {}
        for name, width in RULES[check][0].items():
            local = f'observe_{check}_{name}'
            signals[name] = local
            if name in before:
                observations.append(f'reg [{width-1}:0] {local};')
            else:
                observations.append(f'wire [{width-1}:0] {local} = {current[name]};')
        observations.append('always @(posedge clk) begin')
        # Event is delayed one edge. Before-state and actual redirect are captured
        # at that edge. After-state comes from the core's updated registers.
        for name, expression in before.items():
            if name == 'event':
                expression = f'!reset && ({expression})'
            observations.append(f'{signals[name]} <= {expression};')
        observations.append('end')
        checks[check] = dict(signals=signals, engine='smtbmc bitwuzla')
        if check == 'trap_return':
            checks[check]['least_privileged_mode'] = 3
    captured = raw.decode().replace('endmodule', '\n'+'\n'.join(observations)+'\nendmodule', 1)
    (out/'observed.v').write_text(captured)
    plan = dict(schema='rvw.machine-checks/1', xlen=32, top='VexRiscv', clock='clk', reset='reset',
                sources=['observed.v'], depth=25, checks=checks)
    (out/'machine.json').write_text(json.dumps(plan, indent=2)+'\n')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rtl', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    plan = prepare(args.rtl, args.out)
    out = Path(args.out).resolve()
    if args.run:
        def check(name):
            selected = dict(plan, checks={name:plan['checks'][name]})
            row = run(selected, out, out/name, args.timeout)['rows'][0]
            row['evidence'] = name+'/'+row['evidence']
            return row
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(check, plan['checks']))
        report = dict(schema='rvw.vex-machine-m/1', rtl_sha256=RTL_SHA256, rows=rows,
                      status='fail' if any(r['status']=='failed' for r in rows) else 'inconclusive',
                      limits=['RV32IM FormalMTop export only.',
                              'Three local controller transitions, not full machine signoff.',
                              'Bus, error and interrupt inputs remain unconstrained.',
                              'No CSR instruction, fetch pairing, killed-ID or PC-chain proof.'])
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report))
        return 1 if report['status'] == 'fail' else 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
