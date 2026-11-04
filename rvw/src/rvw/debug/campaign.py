"""Run OpenOCD against a caller-owned simulated JTAG target."""
from pathlib import Path
import re
from rvw.common.proc import run_group

CHECKS = {'halted', 'debug_version', 'abstract_gpr', 'debug_cause', 'running',
          'rehalted', 'unsupported_command', 'clear_cmderr', 'trigger_command',
          'execute_trigger'}


def assess(returncode, output, timed_out=False):
    checks = set(re.findall(r'^RVW_CHECK:(\w+)\s*$', output, re.M))
    complete = 'RVW_COMPLETE:debug-0.13.2-rv64' in output
    if timed_out or not complete:
        status = 'inconclusive'
    elif returncode or checks != CHECKS:
        status = 'fail'
    else:
        status = 'pass'
    return {'status': status, 'scope': 'debug-0.13.2-rv64-reference-client',
            'checks': sorted(checks), 'missing': sorted(CHECKS - checks),
            'timed_out': timed_out, 'returncode': returncode}


def run(config, *, openocd='openocd', timeout=30, log):
    """Config must declare a single RV64 target and call init. Never launch physical I/O by default."""
    suite = Path(__file__).with_name('openocd.tcl')
    result = run_group([openocd, '-f', str(config), '-f', str(suite), '-c', 'shutdown'],
                       timeout=timeout, capture=True)
    output = (result.stdout or '') + (result.stderr or '')
    Path(log).write_text(output)
    return assess(result.returncode, output, result.timed_out)
