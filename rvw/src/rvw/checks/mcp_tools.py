import json
import sys
from pathlib import Path
from rvw.mcp.spec import ToolSpec,ToolError,schema


def run(job,**args):
    argv=[sys.executable,'-m','rvw','checks','generate','--all']
    for key,value in args.items():
        argv += ['--'+key,str(value)]
    code=job.run(argv)
    if code not in (0,3):
        raise ToolError('check generation failed',{'exit_code':code})
    from rvw.common.project import find_project
    project=find_project(args.get('project'))
    out=Path(args['out'])
    if not out.is_absolute(): out=project.parent/out
    return json.loads((out/'result.json').read_text())


def mcp_tools():
    return [ToolSpec('checks_generate','Emit project checks and explicit missing-binding reasons. No proof run.',
            schema({k:{'type':'string'} for k in ('project','out','manifest')},['project','out']),run,long=True)]
