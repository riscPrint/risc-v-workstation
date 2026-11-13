"""Registry-level remote path checks. This is not an OS sandbox."""
from pathlib import Path
from .spec import ToolError

# Shared argument vocabulary, independent of tool names. New providers can use
# format: path or x-rvw-path: true for arguments outside this vocabulary.
PATH_NAMES = set('''abstraction archive artifact artifacts asm backend_sources base baseline
binding bindings blackbox_contract build_dir build_path bundles c1 c2 cache cache_dir
calibration candidate capture catalog checks checkout clock_schedule composition
constants core_config core_repo cosim_platform cost_report coverage cpu_results dat
database db db_path declaration description_path design design_db destination detections
directory dispositions distances edit elf equivalence_test events evidence exclusions
features file findings fix formal functional geometry gold hgldd history hosts include_dirs
index inputs integration inventory irq isa known latencies latency_map library log manifest
map mapping memories memory_spec model new observation observations observed old openapi
oracle original other out output_map pack path payload pdg plan platform policy prediction
previous probes project proof_cache qemu_log ram recipe reference_include reference_source
reference_tree regions replay repo report reports result results resumed revised root rtl
run run_dir runs rvfi sail_config sarif sbt_dir sbt_project scala_root schema sequence
session settings shared_base sim_server smt2 snapshot snapshots soc source source_map
source_repo source_root source_roots sources spec state_plan static_config stimulus store
stream study task tasks template trace trace_out trace_wave traces type_report user_config
verilog wave work_dir workdir'''.split())


def is_path(name, spec):
    return (spec.get('x-rvw-path') is True or spec.get('format') in ('path', 'file-path', 'directory-path')
            or name in PATH_NAMES or name.endswith(('_path', '_dir', '_file', '_root')))


def confine(arguments, schema, project, output=None):
    """Resolve explicit path arguments against the token project before dispatch.

    Walk objects/arrays too. Slash-bearing strings are checked even if an older
    provider omitted path metadata. File contents and command strings are trusted
    inputs under C8; this check does not inspect or rewrite them.
    """
    root = Path(project).expanduser().resolve() if project else None
    if root and (root.is_file() or root.suffix == '.toml'):
        root = root.parent
    roots = [root] if root else []
    if output:
        roots.append(Path(output).expanduser().resolve())

    def walk(value, spec, name=''):
        if isinstance(value, dict):
            props = spec.get('properties', {})
            return {k: walk(v, props.get(k, {}), k) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, spec.get('items', {}), name) for v in value]
        if not isinstance(value, str) or not value:
            return value
        path_arg = is_path(name, spec)
        looks_path = value.startswith(('/', './', '../', '~')) or '/' in value
        if not path_arg and not looks_path:
            # A bare filename can still be a symlink. Workers use this same root.
            if root:
                try:
                    if not (root / value).resolve().is_relative_to(root):
                        raise ToolError(f'path argument {name!r} is outside the bound project')
                except OSError:
                    pass  # Long non-path text is validated by the tool schema.
            return value
        if not root:
            raise ToolError('remote path arguments require a bound project')
        symbolic = spec.get('enum') or name in {'base', 'candidate', 'gold', 'model', 'platform', 'schema', 'policy', 'source', 'reference', 'task', 'formal', 'isa', 'features'}
        path = Path(value).expanduser()
        resolved = (path if path.is_absolute() else root / path).resolve()
        if not any(resolved.is_relative_to(base) for base in roots):
            raise ToolError(f'path argument {name!r} is outside the bound project and output directory')
        return str(resolved) if path_arg and not symbolic else value
    return walk(arguments or {}, schema)
