"""Qualify a campaign's initial C1 suite with the same strict reference checks."""
from pathlib import Path
from rvw.results import load_run
from rvw.cosim.cli import execute_json as cosim
from rvw.regress.random_stream import complete, digest
from . import captured
from .functional import functional
from .campaign_artifacts import execution_identity


@captured.command
def measure(paths, platform, manifest, source_root, core=None, config=None):
    traces, records, native = [], [], None
    run_results = {}
    for path in paths:
        path = Path(path).resolve()
        captured.sha256(path)
        run = load_run(path)
        if (core is not None and run.core != core) or (config is not None and run.config != config):
            raise ValueError('initial C1 core/config differs from the selected project')
        elf = run.artifact('replay_elf') or Path(run.elf)
        if not elf.is_absolute():
            elf = run.path / elf
        trace = run.artifact('rvfi_trace')
        if run.why_inconclusive or run.status != 'pass' or trace is None or digest(elf) != run.elf_sha256:
            raise ValueError('initial run needs passing C1, matching ELF and full C2')
        comparison = cosim('check', elf=str(elf), trace=str(trace), platform=str(platform),
                           model='spike', strict=True, core=run.core)
        if not complete(comparison, run):
            raise ValueError('initial run did not earn a complete strict Spike match')
        identity = execution_identity(run, comparison)
        if native is not None and native != identity:
            raise ValueError('initial runs have different execution identities')
        native = identity
        records.append({'result':str(path), 'result_sha256':digest(path),
                        'elf_sha256':captured.sha256(elf), 'trace_sha256':captured.sha256(trace),
                        'instructions':comparison['instructions'], 'comparison':comparison})
        traces.append(trace)
        run_results[str(Path(trace).resolve())] = path
    if not traces:
        raise ValueError('initial_results must name at least one C1 result')
    coverage = functional(traces, run_results=run_results, platform=platform, manifest=manifest, source_root=source_root)
    return {'records':records, 'execution_identity':native, 'coverage':coverage}
