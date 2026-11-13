#!/usr/bin/env python3
"""Prepare one bounded assertion per selected generated check in a captured design."""
import argparse
import json
from pathlib import Path
import re
import shutil


def prepare(rtl, inventory, out, ids, depth=4, mode="bmc"):
    if mode not in ('bmc', 'prove'):
        raise ValueError('mode must be bmc or prove')
    if not 3 <= depth <= 16:
        raise ValueError('depth must be in 3..16')
    data = json.loads(Path(inventory).read_text())
    if data.get('schema') != 'rvw.checks/1' or data.get('formal') is not True:
        raise ValueError('requires a formal-mode rvw.checks/1 inventory')
    records = {c['id']: c for c in data['checks']}
    selected = [records[key] for key in ids]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    manifest = ['core = "connected-generated-checks"', 'config = "bounded"']
    ident = re.compile(r'[A-Za-z_][A-Za-z0-9_$]*')
    for index, check in enumerate(selected):
        domain = check['clock_domain']
        names = [data['toplevel'], check['fail_signal'].split('.')[-1],
                 domain['clock'].split('.')[-1], domain['reset'].split('.')[-1]]
        if check['status'] != 'inserted' or not all(isinstance(n, str) and ident.fullmatch(n) for n in names):
            raise ValueError('selected checks must have local fail, clock and reset signals')
        if domain['edge'] != 'RISING' or domain.get('clock_enable'):
            raise ValueError('requires an ungated rising clock')
        top, fail, clock, reset = names
        trigger = check.get('trigger_signal')
        if trigger:
            trigger = trigger.split('.')[-1]
            if not ident.fullmatch(trigger):
                raise ValueError('invalid trigger signal')
        owner = check.get('module', top)
        if not ident.fullmatch(owner):
            raise ValueError('invalid owner module')
        if check['path']:
            # A shared module would create several assertions for one selected ID.
            instances = sum(len(re.findall(r'\b' + re.escape(owner) + r'\s+[A-Za-z_][A-Za-z0-9_$]*\s*\(', f.read_text()))
                            for f in Path(rtl).glob('*.v'))
            if instances != 1:
                raise ValueError('nested selected module must have one instance')
        directory = out / str(index)
        directory.mkdir()
        inserted = False
        for src in sorted(Path(rtl).glob('*.v')):
            text = src.read_text()
            module = re.search(r'\bmodule\s+' + re.escape(owner) + r'\b', text)
            if module:
                end = re.search(r'\nendmodule\b', text[module.end():])
                if not end:
                    raise ValueError('top module terminator missing')
                offset = module.end() + end.start()
                active = reset if domain['reset_active'] == 'HIGH' else '!' + reset
                # Reset for the first two formal samples. Other inputs remain arbitrary.
                addition = f'''
reg [1:0] rvw_reset_age = 0;
always @(posedge {clock}) if (rvw_reset_age != 3) rvw_reset_age <= rvw_reset_age + 1'b1;
always @* assume(({active}) == (rvw_reset_age < 2));
rvw_selected_check rvw_selected_check_instance(.clk({clock}), .reset_active({active}), .fail({fail}));
'''
                text = text[:offset] + addition + text[offset:]
                inserted = True
            (directory / src.name).write_text(text)
        if not inserted:
            raise ValueError('selected RTL module missing')
        (directory/'monitor.sv').write_text('module rvw_selected_check(input clk, reset_active, fail);\n'
            'always @(posedge clk) if (!reset_active) assert(!fail);\nendmodule\n')
        extras = [p for p in Path(rtl).iterdir() if p.is_file() and p.suffix in ('.bin', '.hex', '.mem')]
        for source in extras:
            shutil.copyfile(source, directory/source.name)
        files = sorted(p.name for p in directory.glob('*.v'))
        (directory/'job.sby').write_text(f'[options]\nmode {mode}\ndepth {depth}\n\n[engines]\nsmtbmc yices\n\n[script]\n'
            + 'read_verilog -formal -sv ' + ' '.join(files) + '\nchformal -assert -remove\nchformal -cover -remove\n'
            + f'read_verilog -formal -sv monitor.sv\nprep -top {top}\nasync2sync\ndffunmap\n\n[files]\n'
            + '\n'.join(files + sorted(p.name for p in extras)) + '\nmonitor.sv\n')
        manifest += ['', '[[property]]', f'id = "check_{index}"', f'sby = "{index}/job.sby"',
            f'top = "{top}"', 'requirements = [' + json.dumps(check['id']) + ']',
            'assumptions = ["reset for two initial samples; other inputs arbitrary"]']
        if trigger:
            (directory/'activation.sv').write_text(
                'module rvw_selected_check(input clk, reset_active, fail);\n'
                'always @(posedge clk) if (!reset_active) cover(fail);\nendmodule\n')
            job = (directory/'job.sby').read_text()
            cover_job = job.replace('mode ' + mode, 'mode cover').replace('monitor.sv', 'activation.sv')
            activation_files = {}
            occupied = {p.name for p in directory.iterdir()}
            for source in list(directory.glob('*.v')):
                text = source.read_text()
                name = 'activation_' + source.name
                while name in occupied:
                    name = 'activation_' + name
                occupied.add(name)
                (directory/name).write_text(text.replace('.fail(' + fail + ')', '.fail(' + trigger + ')'))
                activation_files[source.name] = name
            # Replace whole tokens once. A.v can also be a suffix of BA.v.
            cover_job = re.sub(r'\S+', lambda token: activation_files.get(token.group(), token.group()), cover_job)
            cover_job = cover_job.replace('chformal -assert -remove', 'chformal -assert -remove\nchformal -cover -remove')
            (directory/'activation.sby').write_text(cover_job)
            manifest.append(f'activation_sby = "{index}/activation.sby"')
    (out/'regress.toml').write_text('\n'.join(manifest)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtl', type=Path, required=True)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check-id', action='append', required=True)
    p.add_argument('--mode', choices=('bmc','prove'), default='bmc')
    p.add_argument('--depth', type=int, default=4)
    a = p.parse_args()
    prepare(a.rtl, a.inventory, a.out, a.check_id, a.depth, a.mode)
