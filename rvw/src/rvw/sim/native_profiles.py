"""Captured opt-in profiles for scalar native probes. No C4 cache reuse."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
from rvw.common.capture import Capture

NAMESPACE='scalar-native-profile-v3'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Profile:
    def __init__(self,path,sources,compiler,verilator,out,*,sdk=None,runtime_mk=None):
        self.env=dict(os.environ);self.flags=[];self.cpp=['-fPIC'];self.link=[];self.compiler=compiler
        self.identity={};self.raw=None;self.request={};self.record={};self.sources=sources
        if path is None:return
        for name in ('CXX','CC','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','MAKEFLAGS','MFLAGS','GNUMAKEFLAGS'):
            if self.env.get(name):raise ValueError('unsupported inherited native profile option: '+name)
        if sdk:self.env['SDKROOT']=sdk
        path=Path(path).resolve(strict=True)
        capture=Capture(out/'captured-profile')
        def frozen(p):
            item=capture.file(Path(p).resolve(strict=True));self.identity[str(item.copy)]=item.sha256;return item.copy
        config=frozen(path);data=json.loads(config.read_text())
        allowed={'schema','threads','hierarchy','ccache','ccache_dir','compiler_pgo','reuse_manifest','training_elf'}
        if data.get('schema')!='rvw.native-build-profile/1' or set(data)-allowed:raise ValueError('unsupported native profile')
        threads=data.get('threads',1);modules=data.get('hierarchy',[]);pgo=data.get('compiler_pgo','off')
        if type(threads) is not int or threads<1 or threads>64:raise ValueError('invalid native thread count')
        if not isinstance(modules,list) or any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',n) for n in modules):raise ValueError('invalid hierarchy boundaries')
        if pgo not in ('off','generate','use'):raise ValueError('unsupported compiler PGO mode')
        self.sources=[frozen(s) for s in sources]
        self.flags=['--threads',str(threads)]
        if modules:
            control=out/'hierarchy.vlt'
            control.write_text('`verilator_config\n'+''.join(f'hier_block -module "{n}"\n' for n in modules))
            self.identity[str(control)]=sha(control)
            self.flags+=['--hierarchical',str(control)]
        basis=dict(namespace=NAMESPACE,rtl=[sha(s) for s in sources],compiler_sha256=sha(compiler),
                   verilator_sha256=sha(verilator),threads=threads,hierarchy=modules,
                   base_flags=['-fPIC','-std=c++17','--x-initial','0','--x-assign','0'])
        if runtime_mk:
            makefile=frozen(runtime_mk)
            basis['verilated_mk_sha256']=sha(makefile)
        if sdk:
            settings=frozen(Path(sdk)/'SDKSettings.json')
            basis['sdk_settings_sha256']=sha(settings)
        if pgo=='generate':
            training=frozen(path.parent/data['training_elf'])
            self.raw=out/'counters.profraw'
            self.env['LLVM_PROFILE_FILE']=str(self.raw)
            self.cpp+=['-fprofile-instr-generate']
            self.link+=['-fprofile-instr-generate']
            self.record=dict(schema='rvw.compiler-pgo-training/1',**basis,training_elf_sha256=sha(training),
                             training_elf=str(training),raw=str(self.raw))
        elif pgo=='use':
            original=(path.parent/data['reuse_manifest']).resolve(strict=True)
            reuse=frozen(original);bound=json.loads(reuse.read_text())
            if bound.get('schema')!='rvw.compiler-pgo/1' or any(bound.get(k)!=v for k,v in basis.items()):raise ValueError('stale compiler profile identity')
            prof=frozen(original.parent/bound['profile'])
            training=frozen(original.parent/bound['training_elf'])
            if sha(prof)!=bound['profile_sha256'] or sha(training)!=bound['training_elf_sha256']:raise ValueError('compiler profile or training ELF digest differs')
            if bound.get('raw_sha256'):
                raw=frozen(original.parent/bound['raw'])
                if sha(raw)!=bound['raw_sha256']:raise ValueError('raw compiler profile digest differs')
            self.cpp+=['-fprofile-instr-use='+str(prof),
                       '-Werror=profile-instr-out-of-date','-Werror=profile-instr-unprofiled']
            self.record=bound
        use_cache=data.get('ccache',False)
        if type(use_cache) is not bool:raise ValueError('ccache must be boolean')
        cache=shutil.which('ccache') if use_cache else None
        if use_cache and not cache:raise ValueError('ccache is not installed')
        if cache:
            self.identity[cache]=sha(cache)
            for name in list(self.env):
                if name.startswith('CCACHE_'):self.env.pop(name)
            directory=(path.parent/data['ccache_dir']).resolve();directory.mkdir(parents=True,exist_ok=True)
            configuration=directory/'ccache.conf';content='max_size = 512M\ncompiler_check = content\nhash_dir = false\n'
            if configuration.exists() and configuration.read_text()!=content:raise ValueError('unexpected private ccache configuration')
            if not configuration.exists():configuration.write_text(content)
            self.env.update(CCACHE_DIR=str(directory),CCACHE_CONFIGPATH=str(frozen(configuration)),
                            CCACHE_BASEDIR=str(out),CCACHE_NOHASHDIR='true')
        wrapper=out/'cxx'
        wrapper.write_text('#!/bin/sh\nexec '+(' '.join(map(shlex.quote,[cache,compiler])) if cache else shlex.quote(compiler))+' "$@"\n')
        wrapper.chmod(0o755);self.compiler=str(wrapper)
        self.identity[str(wrapper)]=sha(wrapper)
        self.flags+=['-MAKEFLAGS','CXX='+shlex.quote(str(wrapper))+((' VM_HIER_VERILATOR='+shlex.quote(verilator)) if modules else '')]
        self.request=data
        self.record=dict(namespace=NAMESPACE,request=data,binding=self.record)
        (out/'profile.json').write_text(json.dumps(self.record,indent=2)+'\n')
        (out/'profile-capture.json').write_text(json.dumps(capture.record(),indent=2)+'\n')
        self.identity[str(out/'profile.json')]=sha(out/'profile.json')
