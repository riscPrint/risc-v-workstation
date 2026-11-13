"""Describe validated C2 capture and configured comparison scope without a model."""
import json
from pathlib import Path
from .trace import Trace
from .platform import Platform
from .checker import SYNC_KINDS, COUNTERS, INSTRET, IRQ_INPUT_MASKS


def execute_json(*, trace, core=None, platform=None, project=None, strict=False):
    try:
        from rvw.common.project import load_project
        selected = load_project(project, core=core)
        if selected:
            core = selected.name
            platform = platform or selected.get('cosim', 'platform')
            if platform is None:
                raise ValueError('project has no cosim.platform')
        if core is None and platform is None:
            raise ValueError('select a project or give --core or --platform')
        p = Platform.load(core or 'reference', Path(platform) if platform else None)
        t = Trace(trace)
        try:
            h = t.header
            if h['xlen'] != p.xlen or h['isa'].lower() != p.isa.lower():
                raise ValueError('trace ISA/XLEN must exactly match the selected platform')
            counts = {}
            instructions = 0
            complete = False
            interrupt_traps = 0
            for row in t:
                kind = row.get('event', 'retirement')
                counts[kind] = counts.get(kind, 0) + 1
                instructions += kind == 'retirement'
                interrupt_traps += kind == 'trap' and row.get('intr', False)
                complete |= kind == 'end'
        finally:
            t.close()
        caps = h.get('capabilities', ['multihart'] if t.multihart else ['state'])
        extended = h['schema'] == 'rvw.rvfi/2'
        checks = {
            'integer': True, 'pc': True, 'privilege': True, 'memory': True,
            'trap': bool(counts.get('trap')), 'interrupt': bool(interrupt_traps),
            'fp': extended and t.state,
            'vector': bool(h.get('vector')), 'vector_memory': bool(h.get('vector_memory')),
            'irq_input_levels': bool(counts.get('irq')), 'hypervisor': bool(h.get('hypervisor')),
            'csr_snapshot': bool(h.get('csr_snapshot')), 'debug': bool(h.get('debug')),
            'fault_access': 'fault' in caps,
        }
        masks = []
        reset_policy = dict(fcsr=p.fcsr_reset, enabled=not strict and p.fcsr_reset == "unspecified" and extended and t.state,
                            scope="once before a neutral first instruction; later values compare exactly")
        if not strict:
            masks += [dict(kind='csr', csr=hex(a), mask=hex(m),
                           reason='platform declares implementation-defined CSR read bits')
                      for a, m in sorted(p.csr_masks.items())]
            masks += [dict(kind='counter', csrs=[hex(a) for a in sorted(COUNTERS - (INSTRET if p.trace_from_reset else set()))],
                           reason='counter reads use DUT timing; instret from reset stays strict'),
                      dict(kind='mmio', regions=[[hex(a), hex(n)] for a, n in p.mmio],
                           reason='loads from declared MMIO regions use DUT data'),
                      dict(kind='irq', inputs=p.irq_inputs,
                           csr_masks={hex(a): hex(m & p.irq_input_mask) for a, m in IRQ_INPUT_MASKS.items() if m & p.irq_input_mask},
                           reason='only DUT 1/reference 0 pending bits with asserted input evidence')]
            if p.trace_from_reset:
                masks.append(dict(kind='csr_reset_unknown', csr='0x340', mask=hex((1 << p.xlen)-1),
                                  reason='only unspecified mscratch reset bits, until defined'))
        masks = [m for m in masks if m['kind'] != 'mmio' or p.mmio]
        return dict(schema='rvw.cosim-doctor/1', status='inspected', compared=False,
                    core=h['core'], config=h['config'], isa=h['isa'], xlen=h['xlen'], reference_profile='spike',
                    trace_schema=h['schema'], capabilities=caps, records=counts,
                    instructions=instructions, trace_complete=complete,
                    csr_snapshot=h.get('csr_snapshot', []), vector=h.get('vector'),
                    comparisons={key: dict(configured=value,
                        reason='captured; requires a capable reference' if value else 'not captured in this trace')
                        for key, value in checks.items()},
                    synchronization_enabled=[] if strict else list(SYNC_KINDS),
                    reset_policy=reset_policy,
                    conditional_masks=masks,
                    platform_policy={key: getattr(p, key) for key in
                        ('privilege_modes', 'pmp_regions', 'absent_pmp_csrs', 'ecall_tval',
                         'illegal_insn_tval', 'misaligned', 'endianness', 'scalar_split_ram')},
                    limits=['No reference was run. Configured comparisons are not matches.',
                            'Conditional masks list allowed synchronization, not applied masks.',
                            'Run cosim check to see applied masks and actual state coverage.',
                            'Strict mode still uses captured DUT-taken interrupt boundaries.'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(schema='rvw.cosim-doctor/1', status='error', compared=False, message=str(exc))


def register(subs):
    cmd = subs.add_parser('doctor', help='inspect C2 capture and configured comparison scope')
    cmd.add_argument('--trace', required=True, type=Path)
    cmd.add_argument('--core')
    cmd.add_argument('--platform', type=Path)
    cmd.add_argument('--strict', action='store_true')
    cmd.add_argument('--json', action='store_true')
    cmd.set_defaults(func=run)


def run(args):
    result = execute_json(trace=args.trace, core=args.core, platform=args.platform,
                          project=getattr(args, 'project', None), strict=args.strict)
    print(json.dumps(result))
    return 2 if result['status'] == 'error' else 0


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('cosim_doctor', 'Inspect validated C2 capture and configured comparison scope. No reference runs or match claims.',
        schema({**{key: {'type': 'string'} for key in ('trace', 'core', 'platform', 'project')},
                'strict': {'type': 'boolean', 'default': False}}, ['trace']), execute_json, isolate=True, annotations={'readOnlyHint': True})]
