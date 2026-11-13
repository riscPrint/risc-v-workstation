"""Adapters retain native output, including diagnostics we cannot parse."""
import re
import shutil
from pathlib import Path
from rvw.common.proc import run_group


def parse(tool, output):
    findings = []
    for line in output.splitlines():
        if tool == "verilator":
            m = re.match(r"%((?:Warning|Error))(?:-([\w]+))?: (.*?):(\d+)(?::(\d+))?: (.*)", line)
            if m:
                level, rule, file, row, col, message = m.groups()
                findings.append(dict(rule=f"verilator.{rule or level.upper()}", severity=level.lower(),
                                     file=file, line=int(row), column=int(col or 1), message=message))
        else:
            m = re.match(r"(.*?):(\d+):(\d+)(?:-\d+)?: (.*?)\s*\[([^\]]+)\]\s*$", line)
            if m:
                file, row, col, message, rule = m.groups()
                findings.append(dict(rule=f"verible.{rule}", severity="warning", file=file,
                                     line=int(row), column=int(col), message=message))
    for finding in findings:
        finding["endpoint"] = f'{finding["file"]}:{finding["line"]}:{finding["column"]}'
    return findings


def run(tool, files, top, timeout):
    executable = shutil.which("verilator" if tool == "verilator" else "verible-verilog-lint")
    if not executable:
        return {"status": "not_run", "reason": "tool not installed", "findings": []}
    command = ([executable, "--lint-only", "-Wall", "-Wno-fatal", "--top-module", top]
               if tool == "verilator" else [executable, "--rules_config_search=false"])
    result = run_group([*command, *files], timeout=timeout, capture=True)
    output = (result.stdout or "") + (result.stderr or "")
    findings = parse(tool, output)
    status = "completed"
    if result.timed_out or result.returncode not in (0, 1) or (result.returncode and not findings):
        status = "inconclusive"
    # A Verilator error is a failed elaboration, even if other warnings were parsed.
    if tool == "verilator" and "%Error" in output:
        status = "inconclusive"
    # Verible can emit style findings and an untagged syntax error in one run.
    # Parsed warnings do not establish that every input was checked.
    if tool == "verible" and any(
            re.match(r".*?:\d+:\d+(?:-\d+)?:", line) and not parse(tool, line)
            for line in output.splitlines()):
        status = "inconclusive"
    version = run_group([executable, "--version"], timeout=10, capture=True)
    return dict(status=status, command=[*command, *files], tool=executable,
                version=(version.stdout or "") + (version.stderr or ""),
                exit_code=result.returncode, timed_out=result.timed_out,
                raw_output=output, findings=findings)


# These rules prescribe source spelling, formatting or optional unused fields.
# Keep functional diagnostics, including truncation and undriven values, unchanged.
GENERATED_ADVICE = {
    'verible.always-comb', 'verible.line-length',
    'verible.explicit-parameter-storage-type', 'verible.unpacked-dimensions-range-ordering',
    'verible.explicit-function-lifetime', 'verible.explicit-function-task-parameter-type',
    'verilator.DECLFILENAME', 'verilator.UNUSEDSIGNAL', 'verilator.UNUSEDPARAM',
}


def summarize_generated(result, files):
    """Count source-style advice on exact RTL files recorded by a Spinal database."""
    generated = {str(Path(f).resolve()) for f in files}
    groups, findings = {}, []
    for f in result['findings']:
        if (f['rule'] not in GENERATED_ADVICE or f['severity'] != 'warning' or
                str(Path(f.get('file') or '').resolve()) not in generated):
            findings.append(f)
            continue
        key = (f['rule'], f['file'])
        if key not in groups:
            groups[key] = dict(f, severity='info', count=0, members=[])
            findings.append(groups[key])
        group = groups[key]
        group['count'] += 1
        group['members'].append({k: f.get(k) for k in ('endpoint', 'file', 'line', 'column')})
    for group in groups.values():
        group['message'] = f"{group['count']} generated-RTL style advisories: " + group['message']
    result['findings'] = findings
    return result
