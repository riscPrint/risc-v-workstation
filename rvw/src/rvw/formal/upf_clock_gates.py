"""Project clock-gate bindings beside literal UPF domains.

These are explicit companion observations, not a new IEEE 1801 Tcl command.
"""
import re
from .power_checks import render

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
RTL = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')
PORTS = {'clk','reset','enable','source_low','clock_edge','work_pending','wakeup'}


def generate(gates, domains, top):
    monitors, binds = [], []
    for name, binding in gates.items():
        if not IDENT.fullmatch(name) or set(binding) != PORTS | {'domain','wake_cycles'}:
            raise ValueError('clock gate needs a literal name, domain, bound and complete observations')
        if binding['domain'] not in domains:
            raise ValueError('clock gate needs a declared UPF domain')
        bound = binding['wake_cycles']
        if type(bound) is not int or not 1 <= bound <= 1024:
            raise ValueError('clock gate wake_cycles must be in 1..1024')
        if any(not isinstance(binding[p],str) or not RTL.fullmatch(binding[p]) for p in PORTS):
            raise ValueError('clock gate observations must be literal RTL paths')
        module = 'rvw_upf_clock_gate_' + name
        monitors.append(render('clock_gate',1,bound).replace('module rvw_clock_gate(', 'module '+module+'('))
        binds.append('bind '+top+' '+module+' '+module+'_instance('+', '.join(
            '.'+p+'('+binding[p]+')' for p in sorted(PORTS))+');')
    return monitors, binds
