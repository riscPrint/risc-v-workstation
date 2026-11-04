"""Bounded C1 artifact and C2/reference checks for an explicit smoke request."""
from pathlib import Path
from rvw.cosim.trace import Trace

OPTIONS = ('rvfi', 'wave', 'coverage', 'konata', 'spinaltrace')


def smoke_options(value):
    selected = list(dict.fromkeys(value.split(','))) if value else []
    if any(x not in OPTIONS for x in selected):
        raise ValueError('smoke options must be a comma-separated list of ' + ','.join(OPTIONS))
    return selected


def artifacts(record, directory, selected, info, *, elf, core, config, platform=None):
    checks = []
    keys = dict(rvfi='rvfi_trace', wave='wave', coverage='coverage', konata='konata', spinaltrace='pdg')
    for option in selected:
        key = keys[option]
        value = record.get('artifacts', {}).get(key)
        path = Path(directory) / value if isinstance(value, str) else None
        valid = (path is not None and not Path(value).is_absolute()
                 and path.resolve().is_relative_to(Path(directory).resolve())
                 and path.is_file() and path.stat().st_size > 0)
        checks.append(dict(name='adapter.artifact.' + key, status='ready' if valid else 'error',
                           detail={'path': value, 'qualification': 'nonempty_artifact_only'},
                           fix='Emit the requested C1 artifact inside the run directory.'))
        if option != 'rvfi' or not valid:
            continue
        trace = None
        try:
            trace = Trace(path)
            header = trace.header
            count, end = 0, None
            for row in trace:
                if 'event' not in row:
                    count += 1
                elif row['event'] == 'end':
                    end = row.get('status')
            valid = (count > 0 and end == record.get('status') == 'pass'
                     and header['core'] == core and header['config'] == config
                     and header['xlen'] == info.get('xlen')
                     and header['isa'] == info.get('isa', {}).get(config))
            detail = dict(instructions=count, end_status=end, header=header,
                          qualification='schema_and_binding_only')
            checks.append(dict(name='adapter.c2', status='ready' if valid else 'error', detail=detail,
                               fix='Emit a complete C2 trace for the requested core, config, ISA and XLEN.'))
            if platform is None:
                checks.append(dict(name='adapter.c2_mapping', status='inconclusive',
                                   detail='No independent reference check requested.',
                                   fix='Supply --smoke-platform with the reviewed core platform JSON.'))
            elif valid:
                from rvw.cosim.cli import execute_json
                comparison = execute_json('check', trace=path, elf=elf, core=core, platform=platform)
                matched = (comparison.get('status') == 'match' and comparison.get('trace_complete') is True
                           and comparison.get('end_status') == 'pass')
                checks.append(dict(name='adapter.c2_mapping', status='ready' if matched else 'error',
                                   detail=comparison, fix='Fix C2 mapping or the reviewed platform inputs; rerun against the reference.'))
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            checks.append(dict(name='adapter.c2', status='error', detail=str(exc), fix='Fix the C2 trace.'))
        finally:
            if trace is not None:
                trace.close()
    return checks
