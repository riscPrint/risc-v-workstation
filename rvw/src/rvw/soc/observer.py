"""Read-only simulation monitor for independently observed transaction tags."""
import hashlib
import json
from pathlib import Path
import re

SIGNALS = ('clock','reset','cycle','request_valid','request_ready','request_tag',
           'request_address','request_write','request_mask','request_data',
           'response_valid','response_ready','response_tag','response_data','response_error',
           'retire_valid','retire_order','retire_tag','retire_count')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    data = json.loads(Path(path).read_text())
    if data.get('schema') != 'rvw.soc-observer/1':
        raise ValueError('expected rvw.soc-observer/1')
    if data.get('data_bytes') not in (1,2,4,8,16) or type(data.get('data_bytes')) is not int:
        raise ValueError('unsupported data_bytes')
    if type(data.get('reset_active_low',False)) is not bool:
        raise ValueError('reset_active_low must be Boolean')
    paths = data['signals']
    if set(paths) != set(SIGNALS) or any(not isinstance(value,str) or not re.fullmatch(
            r'[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*|\[[0-9]+\])*',value) for value in paths.values()):
        raise ValueError('declare every observer signal as a hierarchical path')
    return data


def generate(binding,out):
    data = load(binding)
    root = Path(out);root.mkdir(parents=True,exist_ok=False)
    signal = data['signals'];key = digest(binding)
    active = signal['reset'] if data.get('reset_active_low') else '!'+signal['reset']
    # Values come only from sampled RTL paths. The monitor never reads C2.
    def emit(payload, *args):
        return '$fdisplay(fd, '+json.dumps(payload)+(', '+', '.join(args) if args else '')+');'
    header = dict(schema='rvw.soc-observed-pins/1',binding_sha256=key,run_id='%s',
                  rtl_sha256='%s',elf_sha256='%s',seed='%0d')
    header_text = json.dumps(header,separators=(',',':')).replace('"%0d"','%0d')
    lines = ['module rvw_soc_observer;', 'integer fd; longint seed;',
             'string filename,run_id,rtl_hash,elf_hash;', 'initial begin',
             ' if (!$value$plusargs("RVW_SOC_EVENTS=%s",filename) ||',
             '     !$value$plusargs("RVW_RUN_ID=%s",run_id) ||',
             '     !$value$plusargs("RVW_RTL_SHA256=%s",rtl_hash) ||',
             '     !$value$plusargs("RVW_ELF_SHA256=%s",elf_hash) ||',
             '     !$value$plusargs("RVW_SEED=%d",seed)) $fatal(1,"observer identity plusargs missing");',
             ' fd=$fopen(filename,"w"); if(!fd) $fatal(1,"observer output failed");',
             ' '+emit(header_text,'run_id','rtl_hash','elf_hash','seed'), 'end',
             f'always @(posedge {signal["clock"]}) if ({active}) begin']
    lines += [f' if ({signal["request_valid"]} && {signal["request_ready"]}) '+emit(
        '{"event":"request","cycle":%0d,"tag":"%0h","address":"0x%0h","write":%s,"mask":"0x%0h","data":"0x%0h"}',
        *[signal[k] for k in ('cycle','request_tag','request_address')],
        '('+signal['request_write']+' ? "true" : "false")',signal['request_mask'],signal['request_data'])]
    lines += [f' if ({signal["response_valid"]} && {signal["response_ready"]}) '+emit(
        '{"event":"response","cycle":%0d,"tag":"%0h","data":"0x%0h","error":%s}',
        signal['cycle'],signal['response_tag'],signal['response_data'],
        '('+signal['response_error']+' ? "true" : "false")')]
    lines += [f' if ({signal["retire_valid"]}) begin',
              f'  if ({signal["retire_count"]} !== 1) $fatal(1,"observer requires one bus transaction per retirement");',
              '  '+emit('{"event":"retire_link","cycle":%0d,"order":%0d,"requests":["%0h"]}',
                        signal['cycle'],signal['retire_order'],signal['retire_tag']),
              ' end', ' $fflush(fd);', 'end', 'final begin if(fd) $fclose(fd); end', 'endmodule']
    monitor = root/'observer.sv';monitor.write_text('\n'.join(lines)+'\n')
    report = dict(schema='rvw.soc-observer-generated/1',status='generated',binding=data,
                  binding_sha256=key,monitor_sha256=digest(monitor),
                  limits=['Simulation-only read access. Bind sampled accepted requests and responses.',
                          'Each memory retirement must expose one independently observed transaction tag.',
                          'Tags must be unique for the capture. No address-derived retirement links.',
                          'Cycle, source, RTL, ELF, seed and run identity must agree with independent C1/C2.',
                          'Single-hart, single-beat memory retirement. No DUT qualification is implied.'])
    (root/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def pack(binding,pins,trace,result,out):
    data = load(binding)
    raw = Path(pins).read_bytes()
    records = [json.loads(line) for line in raw.splitlines()]
    if not records:
        raise ValueError('empty RTL pin capture')
    header,events = records[0],records[1:]
    if header.get('schema') != 'rvw.soc-observed-pins/1' or header.get('binding_sha256') != digest(binding):
        raise ValueError('observed pin binding differs')
    run = json.loads(Path(result).read_text())
    run_id = run.get('details',{}).get('simulation_session',{}).get('run_id')
    if not run_id or header.get('run_id') != run_id:
        raise ValueError('observed pins belong to a different run')
    for name in ('rtl_sha256','elf_sha256','seed'):
        if header.get(name) != run.get(name) or (name=='seed' and type(header.get(name)) is not int):
            raise ValueError('observed pin identity differs: '+name)
    if not run.get('source') or not isinstance(run['source'],dict) or not run.get('rtl_sha256') or not run.get('elf_sha256'):
        raise ValueError('missing run source/RTL/ELF identity')
    from rvw.cosim.trace import Trace
    from .pairing import pair_rows
    stream = Trace(trace)
    try:
        if stream.multihart:
            raise ValueError('observer supports single-hart captures')
        pairing = pair_rows(list(stream),events,data['data_bytes'])
    finally:
        stream.close()
    identity = dict(schema='rvw.soc-events/1',observation='rtl_request_response_retire_tags',
                    data_bytes=data['data_bytes'],trace_sha256=digest(trace),run_id=run_id,
                    observed_pins_sha256=hashlib.sha256(raw).hexdigest(),binding_sha256=digest(binding),
                    **{key:run[key] for key in ('source','rtl_sha256','elf_sha256','seed')})
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as target:
        target.write('\n'.join(json.dumps(row,separators=(',',':')) for row in [identity,*events])+'\n')
    return dict(schema='rvw.soc-observer-packed/1',status=pairing['status'],
                capture=str(path),capture_sha256=digest(path),pairs=len(pairing['pairs']),
                gaps=pairing['gaps'],limits=pairing['limits'])
