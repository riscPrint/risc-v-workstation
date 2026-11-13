"""Pair observed request tags with independent architectural memory effects."""
import hashlib
import json
from pathlib import Path
from .model import number


def pair_rows(retirements, events, width):
    if type(width) is not int or width not in (1,2,4,8,16):
        raise ValueError('data_bytes must be 1,2,4,8 or 16')
    requests,responses,links={}, {}, {}
    previous=-1
    for event in events:
        cycle=event['cycle']
        if type(cycle) is not int or cycle<previous:
            raise ValueError('event cycles must be nonnegative and ordered')
        previous=cycle
        kind=event['event']
        if kind=='request':
            tag=event['tag']
            if not isinstance(tag,str) or not tag or tag in requests:
                raise ValueError('request tags must be unique captured transaction identities')
            if type(event['write']) is not bool:
                raise ValueError('request direction must be Boolean')
            address,mask,data=(number(event[key]) for key in ('address','mask','data'))
            if address<0 or address%width or not 0<mask<1<<width or not 0<=data<1<<(width*8):
                raise ValueError('request needs an aligned address and width-bounded data/mask')
            requests[tag]=dict(event,address=address,mask=mask,data=data)
        elif kind=='response':
            tag=event['tag']
            if tag not in requests or tag in responses or type(event['error']) is not bool:
                raise ValueError('response must complete one captured request')
            data=number(event['data'])
            if not 0<=data<1<<(width*8):
                raise ValueError('response data exceeds bus width')
            responses[tag]=dict(event,data=data)
        elif kind=='retire_link':
            order=event['order'];tags=event['requests']
            if type(order) is not int or order<0 or order in links or not isinstance(tags,list) or not tags or len(set(tags))!=len(tags):
                raise ValueError('retire link needs a unique order and nonempty unique request tags')
            if any(tag not in requests for tag in tags):
                raise ValueError('retire link refers to an unobserved request')
            links[order]=event
        else:
            raise ValueError('unknown transaction event')
    rows=[];used=set();gaps=[]
    for row in retirements:
        if 'event' in row:
            continue
        rmask,wmask=row['mem_rmask'],row['mem_wmask']
        if not (rmask or wmask):
            if row['order'] in links:
                raise ValueError('non-memory retirement has a bus link')
            continue
        if rmask and wmask:
            gaps.append(f"order {row['order']}: atomic read/write pairing unsupported")
            continue
        link=links.get(row['order'])
        if link is None:
            gaps.append(f"order {row['order']}: independently observed request tag missing")
            continue
        if link['cycle']!=row['cycle']:
            raise ValueError('retirement link cycle differs from C2')
        observed={};errors=[];checks=[]
        def record(name,actual,expected):
            checks.append(dict(check=name,actual=actual,expected=expected,status='consistent' if actual==expected else 'mismatch'))
        for tag in link['requests']:
            if tag in used:
                raise ValueError('request tag is linked to multiple retirements')
            used.add(tag);req=requests[tag];rsp=responses.get(tag)
            record(tag+':direction',req['write'],bool(wmask))
            record(tag+':request-cycle',req['cycle']<=row['cycle'],True)
            if rsp is None:
                gaps.append(tag+': response missing; error/data comparison incomplete')
            elif req['write'] and rsp['cycle']>row['cycle']:
                gaps.append(tag+': posted-store error reporting needs separate evidence')
            else:
                errors.append(rsp['error'])
                record(tag+':response-cycle',rsp['cycle']<=row['cycle'],True)
            data=req['data'] if req['write'] else rsp['data'] if rsp else None
            for lane in range(width):
                if req['mask'] & 1<<lane:
                    address=req['address']+lane
                    record(tag+f':lane-{lane}-unique',address not in observed,True)
                    observed[address]=(data>>(8*lane))&255 if data is not None else None
        mask=wmask or rmask
        expected={number(row['mem_addr'])+i:(number(row['mem_wdata'] if wmask else row['mem_rdata'])>>(8*i))&255 for i in range(mask.bit_length()) if mask&1<<i}
        record('byte-addresses',sorted(observed),sorted(expected))
        if len(errors)==len(link['requests']):
            record('memory-fault',any(errors),row['mem_fault'])
        if not row['mem_fault'] and not any(errors) and all(value is not None for value in observed.values()):
            record('byte-data',observed,expected)
        rows.append(dict(order=row['order'],requests=link['requests'],checks=checks))
    retired={row['order'] for row in retirements if 'event' not in row}
    if set(links)-retired:
        gaps.append('links without a captured retirement')
    unpaired=sorted(set(requests)-used)
    if unpaired:
        gaps.append('unretired or speculative requests need independent kill/flush evidence')
    if not rows:
        gaps.append('no paired memory retirements')
    mismatch=any(check['status']=='mismatch' for row in rows for check in row['checks'])
    return dict(schema='rvw.soc-pairing/1',status='mismatch' if mismatch else 'inconclusive',
                pairs=rows,unpaired_requests=unpaired,gaps=gaps,
                limits=['Observed request tags are required; address-only matching is refused.',
                        'Little-endian, aligned bus beats; no address translation or atomic pairing.',
                        'Matching samples do not prove decoder, bridge or register semantics.'])


def check(capture,trace,result):
    from rvw.cosim.trace import Trace
    raw=Path(capture).read_bytes();records=[json.loads(line) for line in raw.splitlines()]
    header=records.pop(0)
    if header.get('schema')!='rvw.soc-events/1' or header.get('observation')!='rtl_request_response_retire_tags':
        raise ValueError('requires independently observed RTL request/response/retirement tags')
    run=json.loads(Path(result).read_text())
    if header.get('trace_sha256')!=hashlib.sha256(Path(trace).read_bytes()).hexdigest():
        raise ValueError('capture trace hash differs')
    if not isinstance(run.get('source'),dict) or not run['source'] or not run.get('rtl_sha256') or not run.get('elf_sha256'):
        raise ValueError('capture needs nonempty source, RTL and ELF identity')
    if type(run.get('seed')) is not int or type(header.get('seed')) is not int:
        raise ValueError('capture seed must be an integer')
    for key in ('source','rtl_sha256','elf_sha256','seed'):
        if key not in header or header[key]!=run.get(key):
            raise ValueError('capture run identity differs: '+key)
    if not header.get('run_id') or header['run_id']!=run.get('details',{}).get('simulation_session',{}).get('run_id'):
        raise ValueError('capture simulation session differs')
    stream=Trace(trace)
    try:
        if stream.multihart:
            raise ValueError('multi-hart pairing needs hart-scoped tags')
        retirements=list(stream)
    finally:
        stream.close()
    result=pair_rows(retirements,records,header['data_bytes'])
    result.update(capture_sha256=hashlib.sha256(raw).hexdigest(),trace_sha256=header['trace_sha256'],run_id=header['run_id'])
    return result


def main(args):
    try:
        result=check(args.capture,args.trace,args.result)
        target=Path(args.out)
        if target.exists():
            raise ValueError('output already exists')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result) if args.json else result['status'])
        return 1 if result['status']=='mismatch' else 3
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def register(sub):
    parser=sub.add_parser('pair',help='pair independently observed bus tags with C2 memory retirements')
    parser.add_argument('--capture',required=True)
    parser.add_argument('--trace',required=True)
    parser.add_argument('--result',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=main)


def mcp_tools():
    import sys
    from rvw.mcp.spec import ToolSpec,ToolError,schema
    def execute(job,**args):
        argv=[sys.executable,'-m','rvw','soc','pair']
        for key,value in args.items():
            argv += ['--'+key,str(value)]
        code=job.run(argv)
        path=Path(args['out'])
        if code not in (1,3) or not path.is_file():
            raise ToolError('SoC pairing failed',{'exit_code':code})
        result=json.loads(path.read_text())
        if (code==1)!=(result.get('status')=='mismatch'):
            raise ToolError('SoC pairing exit and report disagree')
        return result
    names=['capture','trace','result','out']
    return [ToolSpec('soc_pair','Pair observed bus request tags with independent C2 retirements. Matching samples remain inconclusive.',
                     schema({key:{'type':'string'} for key in names},names),execute,long=True, side_effects='long-running; writes generated observations or reports to out', native_tools=())]
