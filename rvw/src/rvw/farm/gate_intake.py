"""Fail-closed intake of native C1/C3 evidence for the existing regression gate."""
import hashlib
import re
from pathlib import Path
from rvw.results import load_run
from rvw.results.signature import run_signature
from .recorded_results import recorded_results


def native_identity_issue(run):
    source=run.source
    if source.get('core_dirty') is not False or source.get('tools_dirty') is not False:
        return 'native core and harness must be clean committed revisions'
    for field in ('core_rev_full','tools_rev'):
        if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',str(source.get(field,''))):
            return 'native source revision is missing: '+field
    if not source.get('core_repo') or not source.get('tools_repo'):
        return 'native source repository identity is missing'
    native=run.tools.get('native_build',{})
    if not isinstance(native,dict) or native.get('cache_enabled') is not True:
        return 'native build capture is incomplete'
    for value in (native.get('sha256'),run.elf_sha256,run.extra.get('rtl_sha256')):
        if not re.fullmatch(r'[0-9a-f]{64}',str(value or '')):
            return 'native build, ELF or RTL hash is missing'
    return None


def intake(root):
    suites=recorded_results(root)
    if not suites:
        raise ValueError('no C3 evidence for native farm gate')
    cells=[]
    for suite in suites:
        if suite.extra.get('filter'):
            raise ValueError('filtered_gate: subset evidence does not cover the tier')
        if suite.source.get('identity_complete') is False:
            raise ValueError('C3 source identity is incomplete')
        for test in suite.tests:
            if not test.run:
                raise ValueError('C3 test has no C1 run path')
            directory=Path(test.run)
            if not directory.is_absolute():directory=suite.path/directory
            run=load_run(directory)
            problem=native_identity_issue(run)
            if problem:raise ValueError(problem)
            if run.why_inconclusive or not test.conclusive:
                raise ValueError('inconclusive C1/C3 cannot supply native gate evidence')
            if (run.core,run.config,run.seed,run.status,run.elf_sha256,run.extra.get('rtl_sha256'),run.tools,run_signature(run)) != (
                    suite.core,suite.config,test.seed,test.status,test.extra.get('elf_sha256'),test.extra.get('rtl_sha256'),test.extra.get('tools'),test.signature):
                raise ValueError('C1/C3 native identity or outcome differs: '+test.id)
            options=test.extra.get('options')
            if not isinstance(options,dict):raise ValueError('C3 requested options are missing')
            actual=run.extra.get('options',{}) or {}
            if options.get('rvfi_trace') and run.artifact('rvfi_trace') is None:
                raise ValueError('requested C1 retirement trace is missing')
            for key,wanted in options.items():
                if key in ('max_cycles','mem_latency'):
                    bound=run.get(key)
                elif key in actual:
                    bound=actual[key]
                elif key=='rvfi_trace':
                    bound=run.artifact('rvfi_trace') is not None
                else:
                    raise ValueError('C3 option is not bound by C1: '+key)
                if bound!=wanted:raise ValueError('C1/C3 requested option differs: '+key)
            if test.extra.get('native_options',actual)!=actual:
                raise ValueError('C1/C3 native options differ')
            if any(suite.source.get(k)!=v for k,v in run.source.items()):
                raise ValueError('C1/C3 source identity differs: '+test.id)
            cells.append(dict(test=test.id,seed=test.seed,core_revision=run.source['core_rev_full'],
                harness_revision=run.source['tools_rev'],result_sha256=hashlib.sha256((directory/'result.json').read_bytes()).hexdigest(),
                elf_sha256=run.elf_sha256,rtl_sha256=run.extra['rtl_sha256'],native_build_sha256=run.tools['native_build']['sha256']))
    if not cells:raise ValueError('native gate evidence has no test cells')
    return dict(cells=cells,tests=len(cells))
