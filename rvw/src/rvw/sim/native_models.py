"""Native packed-port models. Project adapters own clocks, buses and C1/C2."""
import ctypes
import hashlib
import json
import os
import time
import resource
import platform
import shlex
from pathlib import Path
import re
import shutil
from rvw.common.proc import run_group

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def step(argv, out, timeout=90, env=None):
    result = run_group(['nice', '-n', '10', *map(str, argv)], timeout=timeout, capture=True, env=env)
    with (out/'build.log').open('a') as f:
        f.write(json.dumps(list(map(str, argv)))+'\n'+result.stdout+result.stderr)
    if result.returncode or result.timed_out or 'PROFOUTOFDATE' in result.stdout+result.stderr:
        raise ValueError('native build failed or timed out; see '+str(out/'build.log'))


class Model:
    def __init__(self, backend, sources, top, ports, out, *, circt=None, profile=None, wave=None):
        if backend not in ('arcilator', 'verilator') or not IDENT.fullmatch(top):
            raise ValueError('unsupported engine or top identifier')
        if not ports or any(not IDENT.fullmatch(n) or d not in ('input','output') or type(w) is not int or not 1 <= w <= 65536
                            for n, (d,w) in ports.items()):
            raise ValueError('ports must have scalar names, directions and widths in 1..65536')
        started=time.monotonic()
        self.profile=None
        self.ports = ports
        self.backend = backend
        self.out = Path(out).resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        sources = [Path(s).resolve(strict=True) for s in sources]
        self.identity = {str(s): hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}
        def tool(name):
            path = str(Path(circt)/'bin'/name) if circt and name in ('circt-verilog','arcilator','llc') else shutil.which(name)
            if not path or not Path(path).is_file(): raise ValueError('missing native tool: '+name)
            self.identity[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            return path
        library = self.out/'model.so'
        if backend == 'arcilator':
            if profile is not None:raise ValueError('build profiles require Verilator')
            step([tool('circt-verilog'), *sources, '--top', top, '--ir-hw', '-o', self.out/'model.mlir'], self.out)
            step([tool('arcilator'), self.out/'model.mlir', '--no-runtime',
                  '--state-file='+str(self.out/'state.json'), '-o', self.out/'model.ll'], self.out)
            step([tool('llc'), '-filetype=obj', '-relocation-model=pic', self.out/'model.ll', '-o', self.out/'model.o'], self.out)
            step([tool('c++'), '-shared', self.out/'model.o', '-o', library], self.out)
            layout = [m for m in json.loads((self.out/'state.json').read_text()) if m['name']==top]
            if len(layout)!=1: raise ValueError('missing or ambiguous model layout')
            layout = layout[0]
            self.states = {s['name']: s for s in layout['states']}
            for name,(direction,width) in ports.items():
                if name not in self.states or (self.states[name]['type'],self.states[name]['numBits']) != (direction,width):
                    raise ValueError('native port layout differs: '+name)
            self.memory = ctypes.create_string_buffer(layout['numStateBytes'])
            self.library = ctypes.CDLL(str(library))
            self.function = getattr(self.library, top+'_eval')
            self.function.argtypes = [ctypes.c_void_p]
            self.function.restype = None
            if layout.get('initialFnSym'):
                initial = getattr(self.library,layout['initialFnSym'])
                initial.argtypes=[ctypes.c_void_p];initial.restype=None;initial(self.memory)
        else:
            from .native_profiles import Profile
            cc=tool(os.environ.get('RVW_NATIVE_CXX','c++'))
            sdk=None
            if profile is not None and platform.system()=='Darwin':
                resolved=run_group(['xcrun','--find',os.environ.get('RVW_NATIVE_CXX','c++')],timeout=15,capture=True)
                if resolved.returncode:raise ValueError('cannot resolve native compiler')
                cc=resolved.stdout.strip()
                sdk_query=run_group(['xcrun','--show-sdk-path'],timeout=15,capture=True)
                if sdk_query.returncode:raise ValueError('cannot resolve compiler SDK')
                sdk=sdk_query.stdout.strip()
                self.identity[cc]=hashlib.sha256(Path(cc).read_bytes()).hexdigest()
            verilator=tool('verilator')
            root = run_group([verilator, '--getenv', 'VERILATOR_ROOT'], timeout=15, capture=True).stdout.strip()
            self.profile=Profile(profile,sources,cc,verilator,self.out,sdk=sdk,runtime_mk=Path(root)/'include/verilated.mk')
            sources=self.profile.sources
            environment=self.profile.env
            cpp=' '.join(shlex.quote(v) for v in self.profile.cpp)
            verilator = tool('verilator')
            root = run_group([verilator, '--getenv', 'VERILATOR_ROOT'], timeout=15, capture=True).stdout.strip()
            obj = self.out/'obj'
            step([verilator, '--cc', '--build', '-j', '2', '--top-module', top, '--prefix', 'RVWModel',
                  '--Mdir', obj, '-Wno-fatal', '--x-initial', '0', '--x-assign', '0', '-CFLAGS', cpp, *self.profile.flags, *sources], self.out, env=environment)
            wrapper = self.out/'wrapper.cpp'
            getters = ''.join(f'case {i}: return m->{name};' for i,(name,(d,w)) in enumerate(ports.items()) if w<=64)
            setters = ''.join(f'case {i}: m->{name}=v; break;' for i,(name,(d,w)) in enumerate(ports.items()) if d=='input' and w<=64)
            wide_getters = ''.join(f'case {i}: for(unsigned j=0;j<{(w+7)//8};++j) b[j]=m->{n}[j/4]>>(8*(j%4)); break;'
                                   for i,(n,(d,w)) in enumerate(ports.items()) if w>64)
            wide_setters = ''.join(f'case {i}: for(unsigned j=0;j<{(w+31)//32};++j) m->{n}[j]=0; for(unsigned j=0;j<{(w+7)//8};++j) m->{n}[j/4]|=uint32_t(b[j])<<(8*(j%4)); break;'
                                   for i,(n,(d,w)) in enumerate(ports.items()) if d=='input' and w>64)
            wrapper.write_text('''#include "RVWModel.h"
#include <cstdint>
double sc_time_stamp(){return 0;}
extern "C" {
void* model_create(){return new RVWModel;}
void model_delete(void* p){delete static_cast<RVWModel*>(p);}
void model_eval(void* p){static_cast<RVWModel*>(p)->eval();}
uint64_t model_read(void* p,unsigned id){auto* m=static_cast<RVWModel*>(p);switch(id){'''+getters+'''default:return 0;}}
void model_write(void* p,unsigned id,uint64_t v){auto* m=static_cast<RVWModel*>(p);switch(id){'''+setters+'''default:break;}}
void model_read_wide(void* p,unsigned id,uint8_t* b){auto* m=static_cast<RVWModel*>(p);switch(id){'''+wide_getters+'''default:break;}}
void model_write_wide(void* p,unsigned id,const uint8_t* b){auto* m=static_cast<RVWModel*>(p);switch(id){'''+wide_setters+'''default:break;}}
}
''')
            if self.profile.raw:
                with wrapper.open('a') as stream:
                    stream.write('extern "C" int __llvm_profile_write_file();\nextern "C" int model_flush_profile(){return __llvm_profile_write_file();}\n')
            includes = Path(root)/'include'
            runtime=obj/'libverilated.a'
            archives=[p for p in sorted(obj.rglob('*.a'),key=lambda p:(p.name!='RVWModel__ALL.a',str(p)))
                      if p.name not in ('libverilated.a','libRVWModel.a')]
            if runtime.exists():
                runtime_link=(['-Xlinker','-force_load','-Xlinker',str(runtime)] if platform.system()=='Darwin'
                              else ['-Xlinker','--whole-archive',str(runtime),'-Xlinker','--no-whole-archive'])
            else:
                if self.profile.request.get('compiler_pgo','off')!='off':
                    raise ValueError('compiler PGO requires the generated runtime archive')
                runtime_link=[str(includes/'verilated.cpp'),str(includes/'verilated_threads.cpp')]
            step([self.profile.compiler, '-std=c++17','-shared',*self.profile.cpp,*self.profile.link,'-pthread','-I'+str(obj),'-I'+str(includes),
                  '-I'+str(includes/'vltstd'), wrapper, *archives, *runtime_link,'-o',library],self.out,env=environment)
            self.identity.update(self.profile.identity)
            if self.profile.raw:os.environ['LLVM_PROFILE_FILE']=str(self.profile.raw)
            self.library=ctypes.CDLL(str(library))
            signatures={'model_create':([],ctypes.c_void_p),'model_delete':([ctypes.c_void_p],None),
                'model_eval':([ctypes.c_void_p],None),'model_read':([ctypes.c_void_p,ctypes.c_uint],ctypes.c_uint64),
                'model_write':([ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint64],None),
                'model_read_wide':([ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p],None),
                'model_write_wide':([ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p],None)}
            for name,(args,result) in signatures.items():
                f=getattr(self.library,name);f.argtypes=args;f.restype=result
            self.memory=self.library.model_create()
            self.ids={n:i for i,n in enumerate(ports)}
        from .native_wave import PortWave
        self.wave = PortWave(wave, ports) if wave is not None else None
        self.evaluations = 0
        self.build_seconds=time.monotonic()-started
        self.child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*(1 if platform.system()=='Darwin' else 1024)
        self.identity[str(library)] = hashlib.sha256(library.read_bytes()).hexdigest()
        (self.out/'identity.json').write_text(json.dumps(self.identity,indent=2)+'\n')

    def write(self,name,value):
        direction,width=self.ports[name]
        if direction!='input' or not 0 <= value < 1<<width: raise ValueError('invalid native input: '+name)
        if self.backend=='arcilator':
            s=self.states[name];size=(width+7)//8
            ctypes.memmove(ctypes.addressof(self.memory)+s['offset'],value.to_bytes(size,'little'),size)
        elif width>64:
            data=ctypes.create_string_buffer(value.to_bytes((width+7)//8,'little'))
            self.library.model_write_wide(self.memory,self.ids[name],data)
        else:self.library.model_write(self.memory,self.ids[name],value)

    def read(self,name):
        width=self.ports[name][1]
        if self.backend=='arcilator':
            s=self.states[name];size=(width+7)//8
            return int.from_bytes(ctypes.string_at(ctypes.addressof(self.memory)+s['offset'],size),'little') & ((1<<width)-1)
        if width>64:
            data=ctypes.create_string_buffer((width+7)//8)
            self.library.model_read_wide(self.memory,self.ids[name],data)
            return int.from_bytes(data.raw,'little') & ((1<<width)-1)
        return self.library.model_read(self.memory,self.ids[name])

    def eval(self):
        if self.backend=='arcilator':self.function(self.memory)
        else:self.library.model_eval(self.memory)
        if self.wave:self.wave.sample(self.evaluations,self.read)
        self.evaluations+=1

    def close(self):
        if self.wave:self.wave.close();self.wave=None
        if self.backend=='verilator' and self.memory:
            if self.profile and self.profile.raw:
                flush=self.library.model_flush_profile;flush.argtypes=[];flush.restype=ctypes.c_int
                if flush()!=0:raise ValueError('compiler profile write failed')
            self.library.model_delete(self.memory);self.memory=None
