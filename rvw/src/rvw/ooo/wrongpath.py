"""Real Spike wrong-path bytes and bounded speculative cache requests."""
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from .core import _instructions, _instruction, simulate
from .project import configuration
from .windows import digest
from .spike_replay import Replay
from rvw.cosim.platform import Platform
from rvw.cosim.trace import Trace


class Work:
    def __init__(self,ops,paths):
        self.positions={id(op):i for i,op in enumerate(ops)}
        self.paths=paths
        self.events=Counter()
    def begin(self,op,cycle,latency,config,instruction_memory):
        path=self.paths.get(self.positions[id(op)])
        if path is None:
            self.events['wrong_path_uncaptured_misses']+=1
            return []
        result=[]
        for wrong in path[:config.fetch_width*latency]:
            self.events['wrong_path_fetched']+=1
            delay=config.frontend.get('fetch_latency',0)+config.frontend.get('decode_latency',1)
            if instruction_memory is not None:
                delay+=instruction_memory.fetch(wrong,cycle)
                self.events['wrong_path_instruction_requests']+=1
            result.append((wrong,cycle+delay))
        return result


def capture(config,trace,elf,platform,max_branches,max_wrong):
    ops=_instructions(Path(trace).read_bytes(),config.custom_instructions)
    paths,records={},[]
    branches=verified=0
    stream=Trace(trace)
    try:
        with Replay(platform,elf) as model:
            if stream.header['xlen']!=platform.xlen:
                raise ValueError('C2 and Spike platform XLEN differ')
            for row in stream:
                if 'event' in row:
                    continue
                effect=model.step()
                observed=platform.normalize_effect(dict(effect))
                for field in ('mode','pc','pc_next','insn','rd','rd_wdata','mem_addr','mem_rmask','mem_wmask','mem_rdata','mem_wdata'):
                    # Unused C2 data/address fields are not architectural effects.
                    if field=='rd_wdata' and not effect['rd']:continue
                    if field=='mem_addr' and not (effect['mem_rmask'] or effect['mem_wmask']):continue
                    if field=='mem_rdata' and not effect['mem_rmask']:continue
                    if field=='mem_wdata' and not effect['mem_wmask']:continue
                    if observed[field]!=row[field]:
                        raise ValueError(f'Spike replay differs at order {row["order"]}: {field}')
                if effect['trap'] or effect['intr']:
                    raise ValueError('committed trapping replay is unsupported')
                verified+=1
                op=ops[verified-1]
                if op.kind not in ('branch','jump') or op.next_pc==op.pc+op.length:
                    continue
                branches+=1
                if len(paths)>=max_branches:continue
                wrong=[];stop='instruction_budget'
                with model.checkpoint() as saved:
                    try:
                        model.redirect(op.pc+op.length)
                        for _ in range(max_wrong):
                            spec=model.step()
                            if spec['trap'] or spec['intr'] or spec['halted']:
                                stop='trap_or_halt';break
                            try:
                                instruction=_instruction(spec,platform.xlen,config.custom_instructions)
                                if instruction.kind not in config.latencies:
                                    raise ValueError('wrong-path latency class is undeclared')
                                wrong.append(instruction)
                            except ValueError:
                                stop='unsupported_instruction';break
                    finally:
                        model.restore(saved)
                paths[verified-1]=wrong
                records.append(dict(order=verified-1,pc=op.pc,predicted_pc=op.pc+op.length,
                                    actual_pc=op.next_pc,stop=stop,instructions=[asdict(w) for w in wrong]))
            identity=model.identity
        if verified!=len(ops):raise ValueError('replay instruction count differs from C2')
        return ops,paths,dict(verified=verified,branch_misses=branches,captured=len(paths),
                              records=records,native_inputs=identity)
    finally:
        stream.close()


def experiment(config,trace,elf,platform,out,max_branches=256,max_wrong_instructions=16,max_cycles=1000000):
    if type(max_branches) is not int or max_branches<1 or type(max_wrong_instructions) is not int or not 1<=max_wrong_instructions<=256:
        raise ValueError('positive branch budget and wrong-instruction budget in [1,256] required')
    c=configuration(json.loads(Path(config).read_text()))
    if c.branch_prediction != 'sequential' or any(k in c.components for k in ('branch','btb','ras','indirect')) or c.frontend.get('fdip'):
        raise ValueError('this experiment requires static sequential targets and no committed-target FDIP')
    if c.rename or c.memory_rename:
        raise ValueError('wrong-path rename elimination and memory renaming are not modeled')
    p=Platform.load("wrong-path",platform)
    ops,paths,captured=capture(c,trace,elf,p,max_branches,max_wrong_instructions)
    baseline=simulate(ops,c,max_cycles,backend='python')
    work=Work(ops,paths)
    actual=simulate(ops,c,max_cycles,backend='python',wrong_path=work)
    actual['events'].update(work.events)
    if baseline['instret']!=actual['instret'] or actual['instret']!=len(ops):
        raise ValueError('speculative work changed architectural retirement count')
    dest=Path(out);dest.mkdir(parents=True,exist_ok=False)
    report=dict(schema='rvw.ooo-wrong-path/1',status='reported',evidence='Spike functional paths and model timing',
                accuracy_status='inconclusive',config_sha256=digest(config),trace_sha256=digest(trace),
                elf_sha256=digest(elf),platform_sha256=digest(platform),capture=captured,
                timing_source_sha256=digest(__file__),
                coverage='all_sequential_misses' if captured['captured']==captured['branch_misses'] else 'bounded_prefix',
                baseline=baseline,wrong_path=actual,
                approximation_gap=dict(cycles=baseline['cycles']-actual['cycles'],
                    ipc_error_percent=100*(baseline['ipc']/actual['ipc']-1),
                    wrong_fetch_estimate=baseline['events'].get('wrong_path_fetch_slots_estimate',0),
                    actual_bounded_wrong_fetches=work.events['wrong_path_fetched']),
                limits=['functional replay restores a single-hart command history, not an RTL checkpoint',
                        'static sequential prediction; bounded wrong-path window at branch issue',
                        'fetch stops at unresolved branch admission; correct-target lookahead is removed',
                        'wrong instruction fetches enter at branch issue within a fetch-width times resolution-latency budget; loads issue through the scheduler',
                        'wrong stores do not write cache or architectural memory',
                        'wrong entries use shared ROB, queues, registers and issue ports, then squash at branch resolution',
                        'fetch requests are batched at branch issue; nested speculative prediction and uop-cache pollution remain unmodeled',
                        'timing gap compares two models; it is not error against RTL'])
    (dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
