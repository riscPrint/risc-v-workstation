"""Native connectivity checks with elaborated bit and source identities."""
import json
from pathlib import Path
import re
import shutil
import tempfile

from rvw.common.proc import run_group


def run(files, top, timeout):
    tool = shutil.which('yosys')
    if not tool:
        return dict(status='not_run', reason='tool not installed', findings=[])
    def quote(path):
        return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'
    with tempfile.TemporaryDirectory(prefix='rvw-lint-') as temp:
        netlist = Path(temp) / 'design.json'
        script = ('read_verilog -sv ' + ' '.join(quote(f) for f in files) + '\n' +
                  f'hierarchy -check -top {top}\nproc\n' +
                  'check\nwrite_json ' + quote(netlist) + '\n')
        plan = Path(temp) / 'lint.ys'
        plan.write_text(script)
        command = [tool, '-Q', '-T', '-s', str(plan)]
        result = run_group(command, timeout=timeout, capture=True)
        output = (result.stdout or '') + (result.stderr or '')
        modules = json.loads(netlist.read_text()).get('modules', {}) if netlist.exists() else {}
    findings = []
    current_module = top
    lines = output.splitlines()
    for index, line in enumerate(lines):
        match = re.search(r'Checking module (\S+)\.\.\.', line)
        if match:
            current_module = match[1]
        if not line.startswith('Warning:'):
            continue
        rule = ('conflicting_drivers' if 'multiple conflicting drivers' in line else
                'combinational_feedback' if 'logic loop' in line else
                'undriven' if 'has no driver' in line else 'warning')
        # Keep all warning text. Resolve exact elaborated wire identities when present.
        wire = re.search(r'[Ww]ire (?:\S+\.\\|\\)([^\s\[]+)', line)
        name = wire[1] if wire else None
        if name is None and 'drivers for ' in line:
            name = line.split('drivers for ', 1)[1].removeprefix(current_module + '.').rstrip(':').removeprefix('\\')
        info = modules.get(current_module, {}).get('netnames', {}).get(name, {})
        source = info.get('attributes', {}).get('src', '')
        loc = re.match(r'(.*?):(\d+)', source)
        related = []
        context = []
        for continuation in lines[index + 1:]:
            if not continuation.startswith('    '):
                break
            context.append(continuation)
            cell = re.match(r'    cell (\S+) ', continuation)
            if cell:
                info_cell = modules.get(current_module, {}).get('cells', {}).get(cell[1], {})
                related.append(dict(endpoint=current_module + '.' + cell[1],
                    source=info_cell.get('attributes', {}).get('src'),
                    bits=sorted({b for values in info_cell.get('connections', {}).values() for b in values}, key=str)))
            for match in re.finditer(r'wire \\([^\s]+)', continuation):
                net = modules.get(current_module, {}).get('netnames', {}).get(match[1], {})
                related.append(dict(endpoint=current_module + '.' + match[1],
                                    source=net.get('attributes', {}).get('src'), bits=net.get('bits', [])))
        findings.append(dict(context=context, related_endpoints=related, rule='yosys.' + rule, severity='warning',
                             endpoint=f'{current_module}.{name}' if name else current_module,
                             file=loc[1] if loc else None, line=int(loc[2]) if loc else None,
                             source=source or None, elaborated_bits=info.get('bits', []), message=line))
    version = run_group([tool, '-V'], timeout=10, capture=True)
    return dict(status='completed' if result.returncode == 0 and not result.timed_out and modules and not any(
                    int(m.get('attributes', {}).get('blackbox', '0'), 2) for m in modules.values()) else 'inconclusive',
                command=command, script=script, version=(version.stdout or '') + (version.stderr or ''),
                exit_code=result.returncode, timed_out=result.timed_out, raw_output=output,
                findings=findings, elaborated_modules=modules)
