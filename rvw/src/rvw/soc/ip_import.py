"""Import a declared Verilog peripheral through a small explicit TOML contract."""
import hashlib
import json
from pathlib import Path
import re
import tomllib
from .model import ident,keys


def signal(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name):
        raise ValueError('invalid Verilog identifier')
    return name


def import_ip(source,root,out,base):
    source=Path(source).resolve();root=Path(root).resolve();out=Path(out).resolve()
    raw=source.read_bytes();spec=tomllib.loads(raw.decode())
    keys(spec,{'schema','name','module','sources','defines','window_size','bus','address_bits','data_bits',
               'address_shift','signals','ports','registers'},
         {'schema','name','module','sources','window_size','bus','address_bits','data_bits','signals','registers'})
    if spec['schema']!='rvw.soc-ip/1' or spec['bus'] not in ('wishbone','apb3'):
        raise ValueError('expected rvw.soc-ip/1 with wishbone or apb3 bus')
    name=ident(spec['name']);module=signal(spec['module']);width=spec['data_bits'];abits=spec['address_bits']
    size=spec['window_size'];shift=spec.get('address_shift',0)
    if width not in (8,16,32) or type(abits) is not int or not 1<=abits<=32:
        raise ValueError('import supports 8/16/32-bit data and 1..32 address bits')
    if type(size) is not int or size<4 or size&(size-1) or type(base) is not int or base<0 or base%size or base+size>2**32:
        raise ValueError('window needs an aligned 32-bit base and power-of-two size')
    if type(shift) is not int or not 0<=shift<=size.bit_length()-1 or abits+shift!=size.bit_length()-1:
        raise ValueError('address port does not cover the window')
    roles={'clock','reset','address','wdata','rdata','write','ready'}
    roles |= {'cycle','strobe'} if spec['bus']=='wishbone' else {'select','enable'}
    mapping=spec['signals'];keys(mapping,roles|{'error','irq','byte_select'},roles)
    for value in mapping.values():signal(value)
    if len(set(mapping.values()))!=len(mapping):raise ValueError('bus ports must have unique roles')
    ports=spec.get('ports',{})
    for port,settings in ports.items():
        signal(port);keys(settings,{'direction','width'},{'direction','width'})
        if port in mapping.values() or settings['direction'] not in ('in','out') or type(settings['width']) is not int or not 1<=settings['width']<=128:
            raise ValueError('invalid external port direction or width')
    registers=spec['registers']
    if not isinstance(registers,list):raise ValueError('registers must be a list')
    for register in registers:
        keys(register,{'name','offset','width','access','reset','write_action','read_action'},{'name','offset','width','access'})
        ident(register['name'])
        register.setdefault('reset',None)
        register.setdefault('read_action','none')
        register.setdefault('write_action','normal')
        if register['access'] not in ('r','w','rw') or register['read_action'] not in ('none','clear') or register['write_action'] not in ('normal','one_to_clear'):
            raise ValueError('unsupported register access or side effect')
        if register['width'] not in (8,16,32) or type(register['offset']) is not int or not 0<=register['offset']<size:
            raise ValueError('register does not fit the window')
    captured={};stack=[]
    def expand(relative):
        path=(root/relative).resolve()
        if not path.is_relative_to(root):raise ValueError('RTL source escapes source root')
        if path in stack:raise ValueError('recursive Verilog include')
        data=path.read_bytes();captured[str(path.relative_to(root))]=hashlib.sha256(data).hexdigest()
        stack.append(path)
        text=data.decode()
        def include(match):return expand(str((path.parent/match[1]).relative_to(root)))
        text=re.sub(r'^\s*`include\s+"([^"\n]+)"[^\n]*$',include,text,flags=re.M)
        stack.pop();return text
    if not isinstance(spec['sources'],list) or not spec['sources']:raise ValueError('sources must name RTL files')
    defines=spec.get('defines',[])
    if not isinstance(defines,list):raise ValueError('defines must be a list')
    bundle=''.join('`define '+signal(d)+'\n' for d in defines)
    bundle+='\n'.join(expand(path) for path in spec['sources'])
    # Clock/reset are explicit active-high inputs in this bounded profile.
    expressions=dict(clock='clk',reset='reset',address=f'address[{abits+shift-1}:{shift}]',
                     wdata=f'wdata[{width-1}:0]',rdata='read_word',write='write',ready='ready')
    expressions.update(error='error',irq='irq',byte_select=f'{width//8}\'h{(1<<(width//8))-1:x}')
    if spec['bus']=='wishbone':expressions.update(cycle='selected && enable',strobe='selected && enable')
    else:expressions.update(select='selected',enable='enable')
    connections=[f'.{port}({expressions[role]})' for role,port in mapping.items()]
    connections += [f'.{port}({port})' for port in ports]
    declarations=[f'{"input" if p["direction"]=="in" else "output"} wire [{p["width"]-1}:0] {n}' for n,p in ports.items()]
    apb_bits=size.bit_length()-1
    wrapper=f'''module rvw_import_{name}(input wire clk, reset,
input wire [{apb_bits-1}:0] address, input wire selected, enable, write,
input wire [31:0] wdata, output wire [31:0] rdata,
output wire ready, error, irq{',' if declarations else ''}{','.join(declarations)});
wire [{width-1}:0] read_word;
assign rdata = read_word;
{'' if 'error' in mapping else "assign error = 1'b0;"}
{'' if 'irq' in mapping else "assign irq = 1'b0;"}
{module} impl({','.join(connections)});
endmodule
'''
    scala=f'''package imported
import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
class {name} extends Component {{
  val io=new Bundle {{
    val bus=slave(Apb3(Apb3Config({apb_bits},32)))
    val irq=out Bool()
'''
    for n,p in ports.items():scala+=f'    val {n}={p["direction"]} Bits({p["width"]} bits)\n'
    scala+='''  }
  val impl=new BlackBox {
'''+f'    setBlackBoxName("rvw_import_{name}")\n'+'''    val io=new Bundle {
      val clk,reset,selected,enable,write=in Bool()
'''+f'      val address=in UInt({apb_bits} bits)\n'+'''      val wdata=in Bits(32 bits)
      val rdata=out Bits(32 bits)
      val ready,error,irq=out Bool()
'''
    for n,p in ports.items():scala+=f'      val {n}={p["direction"]} Bits({p["width"]} bits)\n'
    scala+='''    }
    noIoPrefix()
    mapCurrentClockDomain(clock=io.clk,reset=io.reset)
'''
    # Generated files are local build inputs. Third-party source stays outside Git.
    scala+=f'    addRTLPath({json.dumps(str(out/"bundle.v"))})\n    addRTLPath({json.dumps(str(out/"bridge.v"))})\n  }}\n'
    scala+='''  impl.io.address:=io.bus.PADDR
  impl.io.selected:=io.bus.PSEL.lsb
  impl.io.enable:=io.bus.PENABLE
  impl.io.write:=io.bus.PWRITE
  impl.io.wdata:=io.bus.PWDATA
  io.bus.PRDATA:=impl.io.rdata
  io.bus.PREADY:=impl.io.ready
  io.bus.PSLVERROR:=impl.io.error
  io.irq:=impl.io.irq
'''
    for n,p in ports.items():scala+=f'  {"impl.io."+n if p["direction"]=="in" else "io."+n}:={"io."+n if p["direction"]=="in" else "impl.io."+n}\n'
    scala+='}\n'
    result=dict(schema='rvw.soc-ip-import/1',status='generated',descriptor_sha256=hashlib.sha256(raw).hexdigest(),
        sources=captured,region=dict(name=name,kind='mmio',base=base,size=size,permissions='rw',cacheable=False,registers=registers),
        binder=dict(type='project',**{'class':'imported.'+name},exports=list(ports)),
        validation='generated_only',bus=spec['bus'])
    out.mkdir(parents=True,exist_ok=False)
    for path,text in [('bundle.v',bundle),('bridge.v',wrapper),(name+'.scala',scala),('import.json',json.dumps(result,indent=2)+'\n')]:
        (out/path).write_text(text)
    return result
