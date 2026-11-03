"""Adapters retain native output, including diagnostics we cannot parse."""
import re
import shutil
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
            m = re.match(r"(.*?):(\d+):(\d+)(?:-\d+)?: (.*?)\s+\[([^\]]+)\]\s*$", line)
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
    version = run_group([executable, "--version"], timeout=10, capture=True)
    return dict(status=status, command=[*command, *files], tool=executable,
                version=(version.stdout or "") + (version.stderr or ""),
                exit_code=result.returncode, timed_out=result.timed_out,
                raw_output=output, findings=findings)
