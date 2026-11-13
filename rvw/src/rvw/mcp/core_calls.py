"""Light declarations for the core workflow's cross-package tools.

Keep these fields equal to the providers. test_startup_budget checks them.
The handlers load the original provider on first use.
"""
from .spec import ToolSpec
from .lazy import tool_handler

DECLARATIONS = [{'spec': {'name': 'cosim_check',
           'description': 'Check a recorded C2 RVFI trace against Spike or Sail to locate the '
                          'first architectural mismatch. Preserves synchronization scope and '
                          'matching-prefix/end status. A match does not mean the program passed: '
                          'check end_status. The Sail executable comes from RVW_SAIL on the '
                          'server. Large traces run as a cancellable job.',
           'input_schema': {'type': 'object',
                            'properties': {'project': {'type': 'string',
                                                       'description': 'project file or directory'},
                                           'elf': {'type': 'string',
                                                   'description': 'RISC-V ELF matching the trace '
                                                                  'and platform'},
                                           'core': {'type': 'string',
                                                    'description': 'bundled platform name, or '
                                                                   'label with platform'},
                                           'platform': {'type': 'string',
                                                        'description': 'per-core platform JSON '
                                                                       'path'},
                                           'trace': {'type': 'string'},
                                           'model': {'type': 'string',
                                                     'enum': ['spike', 'sail'],
                                                     'default': 'spike'},
                                           'history': {'type': 'integer',
                                                       'minimum': 0,
                                                       'default': 10},
                                           'strict': {'type': 'boolean',
                                                      'default': False,
                                                      'description': 'disable all synchronization'},
                                           'strict_sync': {'type': 'array',
                                                           'items': {'enum': ['counter',
                                                                              'mmio',
                                                                              'csr',
                                                                              'irq']},
                                                           'description': 'synchronization kinds '
                                                                          'to disable; the others '
                                                                          'stay on'},
                                           'sail_config': {'type': 'string'},
                                           'timeout': {'type': 'number',
                                                       'exclusiveMinimum': 0,
                                                       'default': 120}},
                            'required': ['elf', 'trace'],
                            'additionalProperties': False},
           'long': True,
           'annotations': {'readOnlyHint': True},
           'isolate': False,
           'side_effects': 'long-running; reads trace and ELF; launches selected Spike or Sail '
                           'reference',
           'native_tools': ('Spike', 'Sail'),
           'result_envelope': True},
  'provider': 'rvw.cosim.mcp_tools',
  'wants_job': True},
 {'spec': {'name': 'query_build_db',
           'description': 'Elaborate a design and write its design database (minutes for a CPU). '
                          'Either `design` (a Spinal component class with a no-argument '
                          'constructor, on the classpath of `sbt_dir`, default SpinalDB/spinaldb) '
                          'or `entry` plus `config`: a named entry of SpinalDB/build-db.sh (here: '
                          'boom) and its configuration. An entry holds the machine lock it '
                          'declares. Returns a job id.',
           'input_schema': {'type': 'object',
                            'properties': {'project': {'type': 'string'},
                                           'out': {'type': 'string'},
                                           'design': {'type': 'string'},
                                           'entry': {'type': 'string',
                                                     'description': 'named entry: a directory '
                                                                    'SpinalDB/<entry>'},
                                           'config': {'type': 'string',
                                                      'description': 'configuration of the entry'},
                                           'sbt_dir': {'type': 'string'},
                                           'test_classpath': {'type': 'boolean', 'default': False},
                                           'options': {'type': 'array',
                                                       'items': {'type': 'string'},
                                                       'description': 'extra SpinalDB options, '
                                                                      'e.g. --no-pdg, '
                                                                      '--source-root DIR'}},
                            'required': ['out'],
                            'additionalProperties': False},
           'long': True,
           'annotations': {},
           'isolate': False,
           'side_effects': 'long-running; writes database and build artifacts; launches native '
                           'tools and project build command',
           'native_tools': ('JDK', 'sbt'),
           'result_envelope': True},
  'provider': 'rvw.query.mcp_tools',
  'wants_job': True},
 {'spec': {'name': 'regress_list',
           'description': "Discover a core's suites, tiers and configurations before running; pass "
                          'suite to list test IDs.',
           'input_schema': {'type': 'object',
                            'properties': {'project': {'type': 'string',
                                                       'description': 'project file or directory; '
                                                                      'defaults to RVW_PROJECT or '
                                                                      'discovery'},
                                           'core': {'type': 'string',
                                                    'description': 'core config name or TOML path; '
                                                                   'defaults to RVW_CORE'},
                                           'suite': {'type': 'string'}},
                            'required': [],
                            'additionalProperties': False},
           'long': False,
           'annotations': {'readOnlyHint': True},
           'isolate': False,
           'side_effects': 'read-only',
           'native_tools': (),
           'result_envelope': True},
  'provider': 'rvw.regress.mcp_tools',
  'wants_job': False},
 {'spec': {'name': 'regress_run',
           'description': 'Run suites or a tier through the core adapter, resume/cache results, or '
                          'preview with dry_run. source and rev are mutually exclusive. Use '
                          'regress_compare or regress_gate for an accept/reject decision. Returns '
                          'a job; the runner takes the core lock.',
           'input_schema': {'type': 'object',
                            'properties': {'project': {'type': 'string',
                                                       'description': 'project file or directory; '
                                                                      'defaults to RVW_PROJECT or '
                                                                      'discovery'},
                                           'core': {'type': 'string',
                                                    'description': 'core config name or TOML path; '
                                                                   'defaults to RVW_CORE'},
                                           'jobs': {'type': 'integer', 'minimum': 1},
                                           'seeds': {'type': 'integer', 'minimum': 1},
                                           'seed_base': {'type': 'integer', 'default': 1},
                                           'random_seeds': {'type': 'boolean'},
                                           'filter': {'type': 'array',
                                                      'items': {'type': 'string'},
                                                      'description': 'test-id regexes'},
                                           'max_cycles': {'type': 'integer'},
                                           'timeout': {'type': 'number', 'exclusiveMinimum': 0},
                                           'rvfi_trace': {'type': 'boolean'},
                                           'no_cache': {'type': 'boolean'},
                                           'replay_max_bytes': {'type': 'integer',
                                                                'minimum': 1,
                                                                'description': 'Unique replay ELF '
                                                                               'byte limit; '
                                                                               'default 268435456. '
                                                                               'Checked before '
                                                                               'execution.'},
                                           'suite': {'type': 'string',
                                                     'description': 'comma-separated suites; give '
                                                                    'suite or tier'},
                                           'tier': {'type': 'string'},
                                           'config': {'type': 'string',
                                                      'description': 'comma-separated '
                                                                     'configurations'},
                                           'out': {'type': 'string'},
                                           'rev': {'type': 'string'},
                                           'source': {'type': 'string'},
                                           'fresh': {'type': 'boolean'},
                                           'no_index': {'type': 'boolean'},
                                           'dry_run': {'type': 'boolean'}},
                            'required': [],
                            'additionalProperties': False},
           'long': True,
           'annotations': {},
           'isolate': False,
           'side_effects': 'long-running; launches project native adapter and revision builds; '
                           'writes run artifacts and history under project output',
           'native_tools': (),
           'result_envelope': True},
  'provider': 'rvw.regress.mcp_tools',
  'wants_job': True},
 {'spec': {'name': 'regress_gate',
           'description': 'Gate a change by running a tier on base/candidate revisions or '
                          'comparing stored runs. base and base_rev are mutually exclusive; cand '
                          'and cand_rev are mutually exclusive. Use base_rev or base; candidate '
                          'defaults to HEAD when clean. Dirty trees run but cannot accept: C4 /2 '
                          'reports tests separately and not_accepted_reason=uncommitted. Commit (a '
                          'scratch branch is fine) and rerun; complete RTL identities reuse '
                          'passing results. Returns a job; the runner takes the core lock.',
           'input_schema': {'type': 'object',
                            'properties': {'project': {'type': 'string',
                                                       'description': 'project file or directory; '
                                                                      'defaults to RVW_PROJECT or '
                                                                      'discovery'},
                                           'core': {'type': 'string',
                                                    'description': 'core config name or TOML path; '
                                                                   'defaults to RVW_CORE'},
                                           'known': {'type': 'string'},
                                           'perf_tolerance': {'type': 'number'},
                                           'allow_missing': {'type': 'boolean'},
                                           'seed_policy': {'type': 'string',
                                                           'enum': ['auto', 'exact', 'count'],
                                                           'default': 'auto'},
                                           'jobs': {'type': 'integer', 'minimum': 1},
                                           'seeds': {'type': 'integer', 'minimum': 1},
                                           'seed_base': {'type': 'integer', 'default': 1},
                                           'random_seeds': {'type': 'boolean'},
                                           'filter': {'type': 'array',
                                                      'items': {'type': 'string'},
                                                      'description': 'test-id regexes'},
                                           'max_cycles': {'type': 'integer'},
                                           'timeout': {'type': 'number', 'exclusiveMinimum': 0},
                                           'rvfi_trace': {'type': 'boolean'},
                                           'no_cache': {'type': 'boolean'},
                                           'replay_max_bytes': {'type': 'integer',
                                                                'minimum': 1,
                                                                'description': 'Unique replay ELF '
                                                                               'byte limit; '
                                                                               'default 268435456. '
                                                                               'Checked before '
                                                                               'execution.'},
                                           'budget_cpu_seconds': {'type': 'number',
                                                                  'exclusiveMinimum': 0},
                                           'budget_wall_seconds': {'type': 'number',
                                                                   'exclusiveMinimum': 0},
                                           'budget_job_count': {'type': 'integer', 'minimum': 1},
                                           'cost_report': {'type': 'string'},
                                           'tier': {'type': 'string', 'default': 'quick'},
                                           'config': {'type': 'string'},
                                           'base_rev': {'type': 'string'},
                                           'base': {'type': 'string'},
                                           'cand_rev': {'type': 'string'},
                                           'cand': {'type': 'string'},
                                           'out': {'type': 'string'}},
                            'required': [],
                            'additionalProperties': False},
           'long': True,
           'annotations': {},
           'isolate': False,
           'side_effects': 'long-running; launches project native adapter and revision builds; '
                           'writes run artifacts and history under project output',
           'native_tools': (),
           'result_envelope': True},
  'provider': 'rvw.regress.mcp_tools',
  'wants_job': True}]


def tools(only=None):
    return [ToolSpec(**row['spec'], handler=tool_handler(
                row['provider'], row['spec']['name'], row['wants_job']))
            for row in DECLARATIONS if not only or row['provider'].split('.')[1] in only]
