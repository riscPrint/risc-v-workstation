"""First architectural mismatch to a bounded causal trace."""
from argparse import Namespace
import json
import subprocess
import tempfile
from pathlib import Path
import tomllib

from rvw.runs import open_run
from rvw.runs import adapter
from rvw.bundle.clock import wave_clock, covers
from rvw.cosim.cli import calculate
from rvw.query.db import DesignDB, QueryError
from .vcd import WaveError
from rvw.query.navigation import navigation
from rvw.query.session import Session
from .why import why

FIELDS = {'rd_wdata': 'rd_wdata', 'mem_wdata': 'mem_wdata', 'mem_rdata': 'mem_rdata',
          'rd': 'rd_addr', 'pc': 'pc_rdata', 'pc_next': 'pc_wdata', 'mem_addr': 'mem_addr',
          'insn': 'insn', 'rs1': 'rs1_addr', 'rs2': 'rs2_addr', 'rs1_rdata': 'rs1_rdata',
          'rs2_rdata': 'rs2_rdata', 'mem_rmask': 'mem_rmask', 'mem_wmask': 'mem_wmask',
          'trap': 'trap', 'mode': 'mode'}


def binding_ports(path):
    path = Path(path)
    data = tomllib.loads(path.read_text()) if path.suffix == '.toml' else json.loads(path.read_text())
    if path.suffix == '.toml':
        return data['riscv_formal']['ports']
    if data.get('schema') != 'rvw.rvfi-binding/1':
        raise ValueError('expected rvw.rvfi-binding/1 or a riscv_formal project')
    if data.get('nret', 1) != 1:
        raise ValueError('packed multi-lane RVFI binding needs a lane-specific debug binding')
    return data['ports']


def compare(run, project, platform, timeout):
    trace = run.artifact('rvfi_trace')
    if trace is None:
        raise ValueError('run has no C2 RVFI trace')
    elf = Path(run.get('elf'))
    if not elf.is_absolute():
        elf = run.dir / elf
    return calculate(Namespace(cosim_action='check', trace=trace, elf=elf, core=None if project else run.get('core'),
                              project=project, platform=Path(platform) if platform else None,
                              model='spike', history=10, strict=True, strict_sync=(),
                              timeout=timeout, sail='sail_riscv_sim', sail_config=None))[0]


def explain_run(run_dir, db, binding, out, project=None, platform=None,
                window=20, depth=12, max_nodes=128, timeout=120, rerun=True):
    if window < 1 or depth < 0 or max_nodes < 1 or not 0 < timeout <= 120:
        raise ValueError('window and nodes must be positive; timeout must be in (0,120]')
    run = open_run(run_dir)
    report = compare(run, project, platform, timeout)
    result = {'schema': 'rvw.failure-cause/1', 'status': 'inconclusive', 'cosim': report,
              'accuracy': 'no causal trace', 'limits': []}
    if report.get('status') != 'mismatch':
        result['cause'] = 'Spike did not report an architectural mismatch'
        return result
    mismatch = report['mismatch']
    ports = binding_ports(binding)
    fields = [name for name in mismatch['differences'] if name in FIELDS and FIELDS[name] in ports]
    if not fields:
        result['cause'] = 'no RVFI binding for the mismatching fields'
        return result
    cycle = mismatch['cycle']
    wave = run.artifact('wave')
    clock = wave_clock(run, {}, wave)
    covered, reason = covers(run, wave, cycle, clock)
    if not covered:
        if not rerun:
            result['cause'] = reason
            return result
        cmd = adapter.parse_replay(run.get('replay') or '').set(
            wave=True, rvfi_trace=True, wave_from=max(0, cycle-window), wave_to=cycle+1,
            max_cycles=cycle+2)
        attempt = adapter.execute(cmd, Path(out), core=run.get('core'), timeout=timeout)
        if attempt.run is None:
            result['cause'] = str(attempt.error)
            return result
        replay_report = compare(attempt.run, project, platform, timeout)
        result['replay_cosim'] = replay_report
        replay_mismatch = replay_report.get('mismatch', {})
        if any(replay_mismatch.get(k) != mismatch.get(k) for k in ('order', 'cycle', 'actual', 'differences')):
            result['cause'] = 'replay did not reproduce the same mismatch'
            return result
        run = attempt.run
        wave = run.artifact('wave')
        clock = wave_clock(run, {}, wave)
        covered, reason = covers(run, wave, cycle, clock)
        result['limits'].append('replayed from reset; checkpoint restore is not used')
    if not covered:
        result['cause'] = reason
        return result
    time = clock.time(cycle)
    result.update(cycle=cycle, time=time, clock=clock.to_dict(), chains=[])
    design = DesignDB(db)
    try:
        for field in fields:
            signal = ports[FIELDS[field]]
            nav = navigation(design, signal)
            chain = {'field': field, 'signal': signal, 'navigation': nav}
            chain.update(trace_chain(db, wave, signal, time, max(0, clock.time(cycle-window)),
                                     out, nav['trace']['pdg_available'] or run.artifact('pdg') is not None,
                                     depth, max_nodes, pdg=run.artifact('pdg')))
            result['chains'].append(chain)
    finally:
        design.close()
    usable = any(c.get('dynamic', {}).get('graph', {}).get('vertices') or
                 c.get('driver_walk', {}).get('trace', {}).get('status') == 'active'
                 for c in result['chains'])
    result.update(status='explained' if usable else 'inconclusive',
                  accuracy='candidate causal chains; not a root-cause proof')
    if not usable:
        result['cause'] = 'no active source driver or dynamic graph was resolved'
    result['limits'].append('RVFI binding, database and wave association is caller-selected and unverified')
    return result


def trace_chain(db, wave, signal, time, start, out, instrumented, depth, max_nodes, pdg=None):
    """Trace only the selected window. Remove its wave and index after use."""
    from .index import build
    from .ops import cut
    parent = Path(out).resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='trace-window-', dir=parent) as directory:
        clipped = str(Path(directory) / 'wave.vcd')
        indexed = str(Path(directory) / 'wave.rvwi')
        cut(str(wave), clipped, start, time)
        build(clipped, indexed)
        chain = {'window': {'from': start, 'to': time},
                 'window_boundary': 'history before the wave window is unavailable'}
        if instrumented:
            session = Session(db, indexed)
            try:
                try:
                    chain['dynamic'] = session.trace({'signal': signal, 'time': str(time), **({'pdg': str(pdg)} if pdg else {})})
                except (OSError, ValueError, subprocess.TimeoutExpired, QueryError, WaveError) as exc:
                    chain['dynamic'] = {'status': 'inconclusive', 'cause': str(exc)}
            finally:
                session.close()
        if chain.get('dynamic', {}).get('graph') is not None:
            accuracy = dict(chain['dynamic']['graph'].get('accuracy', {'status': 'unknown'}))
            if start > 0:
                accuracy = {'status': 'incomplete', 'reasons': [*accuracy.get('reasons', []),
                            'History before the selected wave window is unavailable.']}
            chain.update(method='SpinalTrace dynamic dependency graph', accuracy=accuracy)
        else:
            chain.update(driver_walk=why(db, indexed, signal, time, depth, max_nodes, include_control=True),
                         method='database active-driver walk',
                         accuracy='inferred; conditions, memory and window boundaries can be unresolved')
        return chain
