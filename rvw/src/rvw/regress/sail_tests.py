"""Directed RV32 arithmetic tests tied to pinned Sail rules and a DII oracle."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
import socket

from rvw.cosim.dii import Token, exchange
from rvw.cosim.dii_cli import endpoint
from rvw.formal.sail_subset import INSTRUCTIONS, property_trace


def load32(register,value):
    value &= 0xffffffff
    upper=((value+0x800)>>12)&0xfffff
    return [upper<<12 | register<<7 | 0x37,
            (value&0xfff)<<20 | register<<15 | register<<7 | 0x13]


def oracle(connection,words,rd,timeout):
    packets=exchange(connection,[Token(word) for word in words],timeout=timeout)
    if (len(packets)!=len(words) or any(p.trap or p.intr or p.insn!=word or p.order!=i
            for i,(p,word) in enumerate(zip(packets,words))) or packets[-1].rd_addr!=rd
            or not 0<=packets[-1].rd_wdata<2**32):
        raise ValueError('oracle lacks a complete RV32 arithmetic retirement stream')
    return packets[-1].rd_wdata,[asdict(p) for p in packets]


def generate(model,work_dir,sail_endpoint,registers,instructions=None,seed=1,cases=6,timeout=5):
    instructions=instructions or list(INSTRUCTIONS)
    if set(instructions)-set(INSTRUCTIONS) or not instructions:
        raise ValueError('Sail test slice supports add, sub and addi only')
    if (len(registers)!=4 or len(set(registers))!=4 or any(type(r) is not int or not 1<=r<=31 for r in registers)):
        raise ValueError('declare four distinct writable integer registers')
    if type(cases) is not int or not 1<=cases<=128 or type(seed) is not int or not 0<=seed<2**32:
        raise ValueError('cases must be 1..128 and seed must be uint32')
    obligations={name:property_trace(model,name) for name in instructions}
    out=Path(work_dir);out.mkdir(parents=True,exist_ok=False)
    report={'schema':'rvw.sail-directed-tests/1','status':'inconclusive','seed':seed,
            'oracle_endpoint':sail_endpoint,'reference_identity_verified':False,'cases':[],
            'notes':['Pinned rule links and remote reference observations do not grant DUT pass.',
                     'The endpoint binary identity is not attested. Only the three pinned RV32 arithmetic rules are supported.']}
    rng=random.Random(seed)
    boundaries=[0,1,0x7fffffff,0x80000000,0xffffffff]
    rd,a,b,expected=registers
    def save():
        (out/'tests.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        with socket.create_connection(endpoint(sail_endpoint),timeout) as connection:
            for index in range(cases):
                name=instructions[index%len(instructions)]
                av=boundaries[index%len(boundaries)] if index<len(boundaries) else rng.getrandbits(32)
                bv=1 if index<len(boundaries) else rng.getrandbits(32)
                word=((bv&0xfff)<<20 | a<<15 | rd<<7 | 0x13) if name=='addi' else (
                    (0x40000033 if name=='sub' else 0x33) | b<<20 | a<<15 | rd<<7)
                setup=load32(a,av)+load32(b,bv)
                words=setup+[word]
                case={'id':f'{name}-{index}','instruction':name,'obligation':obligations[name],
                      'words':words,'status':'inconclusive'}
                report['cases'].append(case)
                raw=b''.join(Token(w).encode() for w in words)+Token(cmd=0).encode()
                (out/(case['id']+'.dii')).write_bytes(raw)
                value,packets=oracle(connection,words,rd,timeout)
                case.update(expected=value,reference_packets=packets,status='reference_generated',
                            tokens_sha256=sha256(raw).hexdigest())
                mutants=[]
                for kind,mutant in [('instruction',word ^ (1<<20 if name=='addi' else 1<<30)),
                                    ('operand_register',word ^ (1<<15))]:
                    changed,_=oracle(connection,setup+[mutant],rd,timeout)
                    mutants.append({'kind':kind,'word':mutant,'reference_result':changed,'detected':changed!=value})
                case['mutants']=mutants
                check=load32(expected,value)
                assembly=('.option norvc\n.option norelax\n'+
                          ''.join(f'.word 0x{w:08x}\n' for w in words+check)+
                          f'bne x{rd}, x{expected}, rvw_test_fail\n')
                path=out/(case['id']+'.S');path.write_text(assembly)
                case.update(source=str(path),source_sha256=sha256(assembly.encode()).hexdigest())
                save()
        report['status']='reference_generated'
    except (OSError,ValueError,EOFError,TimeoutError) as exc:
        report['reason']=str(exc)
    save()
    return report


def execute_json(action='sail-tests',**options):
    if action!='sail-tests':
        raise ValueError('unknown Sail test action')
    return generate(**options)


def run(args):
    try:
        result=generate(args.model,args.work_dir,args.sail_endpoint,[int(r) for r in args.registers.split(',')],
                        args.instructions,args.seed,args.cases,args.timeout)
        code=0 if result['status']=='reference_generated' else 3
    except (ValueError,OSError) as exc:
        result,code={'status':'error','message':str(exc)},2
    print(json.dumps(result,indent=2))
    return code


def register(sub):
    parser=sub.add_parser('sail-tests',help='generate directed tests for three pinned RV32 Sail arithmetic rules')
    parser.add_argument('--model',required=True)
    parser.add_argument('--work-dir',required=True)
    parser.add_argument('--sail-endpoint',required=True)
    parser.add_argument('--registers',required=True)
    parser.add_argument('--instructions',nargs='+',choices=list(INSTRUCTIONS))
    parser.add_argument('--seed',type=int,default=1)
    parser.add_argument('--cases',type=int,default=6)
    parser.add_argument('--timeout',type=float,default=5)
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=run)
