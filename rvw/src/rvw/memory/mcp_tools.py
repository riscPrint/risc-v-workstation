from rvw.mcp.spec import ToolSpec, schema


def mcp_tools():
    return [ToolSpec('memory_concurrent_smoke', 'Run a bounded native Spike completion smoke; ordering and RTL remain unchecked.',
                     schema({'out': {'type': 'string'}, 'seed': {'type': 'integer', 'default': 1},
                             'harts': {'type': 'integer', 'default': 2}, 'length': {'type': 'integer', 'default': 16},
                             'gcc': {'type': 'string', 'default': 'riscv64-unknown-elf-gcc'},
                             'spike': {'type': 'string', 'default': 'spike'}, 'timeout': {'type': 'number', 'default': 30}},
                            required=['out']), concurrent_smoke,
        side_effects='long-running; launches compiler and Spike; writes smoke artifacts under out', native_tools=('RISC-V GCC', 'Spike'),
        ),
            ToolSpec('memory_directory', 'Check a finite queued MESI/MOESI directory model with named weak fairness.',
                     schema({'profile': {'type': 'string', 'default': 'mesi'}, 'lines': {'type': 'integer', 'default': 1},
                             'requests': {'type': 'integer', 'default': 1}, 'limit': {'type': 'integer', 'default': 100000},
                             'bug': {'type': 'string'} }), directory_check,
        side_effects='read-only; long-running finite model search', native_tools=(),
        ),
            ToolSpec('memory_tilelink_bind', 'Generate a bounded two-client TL-C complete-message monitor and bind from SpinalDB.',
                     schema({'database': {'type': 'string'}, 'profile': {'type': 'string'}, 'out': {'type': 'string'}},
                            required=['database', 'profile', 'out']), tilelink_bind,
        side_effects='writes generated monitor and binding under out', native_tools=(),
        ),
            ToolSpec('memory_axiomatic', 'Search scalar RVWMO/Ztso execution graphs with complete dependency observations.',
                     schema({'trace': {'type': 'string'}, 'reference': {'type': 'string'},
                             'model': {'type': 'string', 'default': 'rvwmo'}, 'limit': {'type': 'integer', 'default': 100000}},
                            required=['trace', 'reference']), axiomatic_check,
        side_effects='read-only; long-running graph search', native_tools=(),
        ),
            ToolSpec('memory_generate', 'Generate seeded concurrent RV64 fragments. Does not execute them.',
                     schema({'seed': {'type': 'integer', 'default': 1}, 'harts': {'type': 'integer', 'default': 2},
                             'length': {'type': 'integer', 'default': 16}}), generate,
        side_effects='read-only; generates fragments in memory', native_tools=(),
        ),
            ToolSpec('memory_images', 'Prepare pinned per-hart ELF inputs. Does not run a DUT.',
                     schema({'hart_images': {'type': 'array', 'items': {'type': 'string'}}}, required=['hart_images']), images,
        side_effects='read-only', native_tools=(),
        ),
            ToolSpec('memory_check', 'Check C2/2 serialized memory against independent stimulus bytes. No RVWMO proof.',
                     schema({'trace': {'type': 'string'}, 'reference': {'type': 'string'}}, required=['trace', 'reference']), check,
        side_effects='read-only', native_tools=(),
        )]


def check(trace, reference):
    """Load the handler on first use."""
    from rvw.memory.multihart import check as implementation
    return implementation(trace, reference)

def images(hart_images):
    """Load the handler on first use."""
    from rvw.memory.multihart import images as implementation
    return implementation(hart_images)

def axiomatic_check(trace, reference, model='rvwmo', limit=100000):
    """Load the handler on first use."""
    from rvw.memory.axiomatic import check as implementation
    return implementation(trace, reference, model, limit)

def generate(seed=1, harts=2, length=16):
    """Load the handler on first use."""
    from rvw.memory.concurrent import generate as implementation
    return implementation(seed, harts, length)

def tilelink_bind(database, profile, out):
    """Load the handler on first use."""
    from rvw.memory.tilelink_bind import generate as implementation
    return implementation(database, profile, out)

def directory_check(profile='mesi', lines=1, requests=1, limit=100000, bug=None):
    """Load the handler on first use."""
    from rvw.memory.directory_model import check as implementation
    return implementation(profile, lines, requests, limit, bug)

def concurrent_smoke(out, seed=1, harts=2, length=16, gcc='riscv64-unknown-elf-gcc', spike='spike', timeout=30):
    """Load the handler on first use."""
    from rvw.memory.concurrent_native import smoke as implementation
    return implementation(out, seed, harts, length, gcc, spike, timeout)
