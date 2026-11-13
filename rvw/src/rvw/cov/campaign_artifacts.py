"""Immutable attempt evidence and stable execution identities."""
from hashlib import sha256
import json
import os
import shutil
from pathlib import Path
from rvw.results.generation import publish,open_generation
from . import captured


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def implementation_id():
    package=Path(__file__).parent
    files={str(path.relative_to(package.parent)):captured.sha256(path) for path in package.glob('*.py')}
    from rvw.common import riscv
    files['common/riscv.py']=captured.sha256(riscv.__file__)
    return digest(files)


def reference_identity(reproduction,volatile_paths=()):
    capture=reproduction.get('capture',{})
    if capture.get('schema')!='rvw.capture/1' or capture.get('problems'):
        raise ValueError('reference dependency capture is missing or incomplete')
    payload={reproduction.get(k) for k in ('elf_sha256','trace_sha256')}
    volatile={str(Path(p).resolve()) for p in volatile_paths}
    if reproduction.get('trace') and reproduction.get('core_run') is not None:
        volatile.add(str(Path(reproduction['trace']).parent/'result.json'))
    files=sorted((r['resolved'],r['sha256']) for r in capture.get('files',[])
                 if r['sha256'] not in payload and r['resolved'] not in volatile)
    trees=[]
    for tree in capture.get('trees',[]):
        # Interpreter caches can appear after an import without changing the implementation.
        entries=sorted((r['resolved'],r['sha256']) for r in tree['files']
                       if '__pycache__' not in Path(r['resolved']).parts
                       and Path(r['resolved']).suffix not in ('.pyc','.pyo'))
        trees.append((tree['resolved'],entries))
    tools=sorted((r['resolved'],r['sha256'],json.dumps(r.get('version'),sort_keys=True)) for r in capture.get('tools',[]))
    if not files or not tools:
        raise ValueError('reference files and native tool identities are required')
    return digest({'files':files,'trees':sorted(trees),'tools':tools,'env':capture.get('env'),
                   'tools_rev':reproduction.get('tools_rev')})


def execution_identity(run,comparison):
    source=run.source
    capture=run.extra.get('input_capture',{})
    rtl=run.extra.get('rtl_sha256')
    if (not run.core or not run.config or not run.tools or source.get('identity_complete') is False or source.get('core_identity_covered') is False
            or not source.get('tools_key') or capture.get('inputs_key')!=source['tools_key']
            or capture.get('elf_sha256')!=run.elf_sha256 or not isinstance(rtl,str)
            or len(rtl)!=64 or any(c not in '0123456789abcdef' for c in rtl)):
        raise ValueError('C1 source/native input identity is missing or incomplete')
    stable_source={k:v for k,v in source.items() if k.startswith('core_')}
    return digest({'core':run.core,'config':run.config,'source':stable_source,
                   'inputs_key':source['tools_key'],'rtl_sha256':rtl,'tools':run.tools,
                   'reference':reference_identity(comparison.get('reproduction',{}),
                       [run.path/'result.json'] if getattr(run,'path',None) else [])})


def seal_attempt(out,directory,attempt):
    store=out/'attempt-evidence'/directory.name
    names=attempt['artifacts']
    metadata={key:attempt.get(key) for key in ('goal','seed','status','artifacts')}
    def build(target):
        for name,expected in names.items():
            source=out/name
            content=source.read_bytes()
            if sha256(content).hexdigest()!=expected:
                raise ValueError('attempt artifact changed before publication: '+name)
            path=target/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(content);os.chmod(path,source.stat().st_mode&0o777)
        (target/'attempt.json').write_text(json.dumps(metadata,indent=2)+'\n')
    identifier=publish(store,build)
    generation=open_generation(store,identifier)
    return {'store':str(store.relative_to(out)),'id':identifier,'manifest_sha256':generation.manifest_sha256}


def verify_attempt(out,attempt):
    seal=attempt.get('sealed_generation')
    if seal is None:
        if attempt.get('artifacts'):
            raise ValueError('resume attempt has no sealed raw evidence')
        return
    store=Path(seal['store'])
    if store.is_absolute() or '..' in store.parts:
        raise ValueError('invalid sealed attempt store')
    generation=open_generation(out/store,seal['id'])
    if generation.manifest_sha256!=seal['manifest_sha256']:
        raise ValueError('sealed attempt manifest changed')
    metadata=json.loads(generation.read_bytes('attempt.json'))
    if metadata!={key:attempt.get(key) for key in ('goal','seed','status','artifacts')}:
        raise ValueError('sealed attempt metadata differs')
    for name,expected in attempt.get('artifacts',{}).items():
        if sha256(generation.read_bytes(name)).hexdigest()!=expected:
            raise ValueError('sealed attempt artifact changed: '+name)


def seal_inputs(out,identity):
    capture=captured.current()
    store=out/'input-evidence'
    record={'identity':identity,'capture':capture.record()}
    def build(target):
        shutil.copytree(capture.root,target/'input-capture')
        (target/'inputs.json').write_text(json.dumps(record,indent=2)+'\n')
    identifier=publish(store,build)
    generation=open_generation(store,identifier)
    return {'store':str(store.relative_to(out)),'id':identifier,'manifest_sha256':generation.manifest_sha256}


def verify_inputs(out,seal,identity):
    store=Path(seal['store'])
    if store.is_absolute() or '..' in store.parts:
        raise ValueError('invalid sealed input store')
    generation=open_generation(out/store,seal['id'])
    if generation.manifest_sha256!=seal['manifest_sha256'] or json.loads(generation.read_bytes('inputs.json'))['identity']!=identity:
        raise ValueError('sealed campaign inputs changed')
