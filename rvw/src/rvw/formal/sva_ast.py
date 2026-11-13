"""Native typed SVA inspection without RTL lowering or a proof claim."""
from argparse import Namespace
from collections import Counter
import json
import math
import os
from pathlib import Path

from rvw.common.capture import Capture
from rvw.common.proc import run_group
from . import common
from .snapshot import InputSnapshot
from .tools import _ENV


def summarize(tree):
    if not isinstance(tree,dict) or tree.get('kind')!='Root':
        raise ValueError('native AST must contain a Root object')
    kinds,operators=Counter(),Counter()
    properties=[]
    def walk(value,path='$'):
        if isinstance(value,dict):
            if isinstance(value.get('kind'),str):
                kinds[value['kind']]+=1
            if isinstance(value.get('op'),str):
                operators[value['op']]+=1
            if value.get('kind')=='ConcurrentAssertion':
                properties.append(dict(index=len(properties),node_path=path,
                                       assertion_kind=value.get('assertionKind','unknown')))
            for key,child in value.items():
                walk(child,path+'.'+key)
        elif isinstance(value,list):
            for index,child in enumerate(value):
                walk(child,f'{path}[{index}]')
    walk(tree)
    return dict(properties=properties,node_kinds=dict(sorted(kinds.items())),
                operators=dict(sorted(operators.items())))


def dependency_status(path,snapshot):
    if not path.is_file():
        return dict(status='inconclusive',cause='missing_native_dependency_report')
    read={str((snapshot.out/line).absolute()) if not Path(line).is_absolute() else line
          for line in path.read_text().splitlines() if line}
    allowed={str(snapshot.out/row['frontend']) for row in snapshot.files if 'frontend' in row}
    if not set(map(str,snapshot.sources))<=read or read-allowed:
        return dict(status='error',cause='unsealed_native_source_dependencies')
    return dict(status='verified',files=sorted(read))


def run(args):
    with common.sigterm_raises():
        return _run(args)


def _run(args):
    common.check_ident('top',args.top)
    if not args.timeout>0 or not math.isfinite(args.timeout):
        raise ValueError('timeout must be positive and finite')
    selected=args.plugin or os.environ.get('RVW_SLANG')
    if not selected:
        raise ValueError('set RVW_SLANG or pass --plugin for native AST inspection')
    plugin_path=common.check_path('plugin',selected)
    out=common.check_path('out',args.out)
    if plugin_path.resolve().is_relative_to((out/'compiler-inputs').resolve()):
        raise ValueError('plugin is inside the owned compiler capture; use another --out')
    fd=common.lock_out(out)
    try:
        common.clear_outputs(out,'result.json','ast.json','compiler-inputs','native-deps.txt',
                             'inspect.ys','stdout.log','stderr.log')
        snapshot=InputSnapshot(Namespace(verilog=args.verilog,checks=None,frontend='verilog'),out)
        compiler=Capture(out/'compiler-inputs')
        saved=compiler.env(*_ENV,'RVW_SLANG')
        env={key:value for key,value in saved.items() if value is not None}
        yosys=compiler.tool(common.need('yosys'))
        plugin=compiler.file(plugin_path)
        script=out/'inspect.ys'
        script.write_text('plugin -i '+str(common.check_path('captured plugin',plugin.copy))+'\n'
                          'read_slang --no-synthesis-define --no-default-translate-off-format '
                          '--dump-ast --ast-compilation-only --top '+args.top+
                          ' --all-deps '+str(out/'native-deps.txt')+' '+
                          ' '.join(str(path) for path in snapshot.sources)+'\n')
        snapshot.seal(script)
        with (out/'stdout.log').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
            completed=run_group(['nice','-n','10',str(yosys.path),'-Q','-T','-q','-s',str(script)],
                                cwd=out,env=env,stdout=stdout,stderr=stderr,timeout=args.timeout)
        result=dict(schema='rvw.sva-inspection/1',status='error',top=args.top,
                    proof_status='not_run',lowering_status='not_run',properties=[],
                    artifacts=dict(stdout='stdout.log',stderr='stderr.log'),
                    compiler=dict(yosys_sha256=yosys.sha256,version=yosys.version.strip(),
                                  plugin_sha256=plugin.sha256),
                    limits=['Native AST inspection only; no RTL lowering or proof.',
                            'Native AST addresses are process-local, not persistent property identities.',
                            'Runtime libraries are not sealed by this inspection command.'])
        if completed.timed_out:
            result.update(status='timeout',cause='native_compilation_timeout')
        elif completed.returncode==0:
            try:
                text=(out/'stdout.log').read_text()
                tree,_=json.JSONDecoder().raw_decode(text.lstrip())
                detail=summarize(tree)
                ast=out/'ast.json'
                ast.write_text(json.dumps(tree,indent=2)+'\n')
                snapshot.seal(ast)
                closure=dependency_status(out/'native-deps.txt',snapshot)
                result.update(detail,input_closure=closure)
                result['artifacts']['ast']='ast.json'
                result['status']=('error' if closure['status']=='error' else
                                  'no_checks' if not detail['properties'] else
                                  'parsed' if closure['status']=='verified' else closure['status'])
                if 'cause' in closure:
                    result['cause']=closure['cause']
            except (ValueError,OSError) as error:
                result.update(status='error',cause='invalid_native_ast',diagnostic=str(error))
        else:
            result.update(cause='native_compilation_failed',returncode=completed.returncode)
        compiler.verify_tools()
        result['compiler_capture']=compiler.record()
        snapshot.finish(result)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        return 0 if result['status']=='parsed' else 1
    finally:
        os.close(fd)
