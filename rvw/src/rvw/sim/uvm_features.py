"""Explicit capability boundary of the pinned UVM conformance runner.

An unsupported diagnostic describes this runner profile. It does not claim
that every version of the simulator lacks the language feature.
"""
SUPPORTED = frozenset(('phases', 'config_db', 'factory_create', 'tlm',
                       'bounded_constraints', 'basic_covergroups', 'ral_frontdoor'))
UNSUPPORTED = {
    'dpi_dynamic_arrays': ('unsupported:uvm_dpi_dynamic_arrays', 'use fixed arrays with an explicit element count'),
    'hdl_backdoor': ('unsupported:uvm_hdl_backdoor', 'use a tested custom uvm_reg_backdoor'),
    'vpi_polling': ('unsupported:uvm_vpi_polling', 'use an explicit project observation interface'),
    'dpi_regex': ('unsupported:uvm_dpi_regex', 'use portable exact config names; UVM_NO_DPI disables regex DPI'),
    'four_state': ('unsupported:uvm_four_state', 'use an event-driven four-state engine for X/Z checks'),
    'advanced_constraints': ('unsupported:uvm_advanced_constraints', 'use seeded explicit generators or qualify a dedicated SV probe'),
    'advanced_coverage': ('unsupported:uvm_advanced_coverage', 'use explicit bins and rvw cov functional coverage'),
    'phase_jumps': ('unsupported:uvm_phase_jumps', 'use reset and test sequencing without phase jumps'),
    'factory_overrides': ('unsupported:uvm_factory_overrides', 'use explicit component construction until separately qualified'),
    'callbacks': ('unsupported:uvm_callbacks', 'use explicit monitor and analysis connections'),
    'field_automation': ('unsupported:uvm_field_automation', 'implement explicit copy and compare methods'),
    'assertion_liveness': ('unsupported:uvm_assertion_liveness', 'use bounded simulation checks or rvw formal'),
    'commercial_vip': ('unsupported:uvm_commercial_vip', 'use project agents with dedicated conformance tests'),
    'cpu_interrupt_compare': ('unsupported:uvm_cpu_interrupt_compare', 'use the architectural interrupt checker with C2 events'),
    'cpu_debug_compare': ('unsupported:uvm_cpu_debug_compare', 'use a dedicated debug checker and captured observations'),
    'cpu_csr_snapshots': ('unsupported:uvm_cpu_csr_snapshots', 'use rvw csr checks or an extended reference comparator'),
}


def require(features):
    for feature in features:
        if feature in UNSUPPORTED:
            diagnostic, workaround = UNSUPPORTED[feature]
            raise ValueError(f'{diagnostic}: {workaround}')
        if feature not in SUPPORTED:
            raise ValueError(f'unsupported:uvm_unknown_feature: {feature}')


def markdown():
    lines = ['| Feature | Profile diagnostic | Workaround |', '|---|---|---|']
    for feature, (diagnostic, workaround) in UNSUPPORTED.items():
        lines.append(f'| {feature} | `{diagnostic}` | {workaround} |')
    return '\n'.join(lines)+'\n'
