"""Small editable SoC project with a deliberate non-executing core wrapper."""
import json
import os
from pathlib import Path
from .model import ident,dumps


def new(name,out):
    ident(name)
    target=Path(out)
    if target.exists(): raise ValueError('scaffold output must be new')
    home=Path(os.environ.get('RVW_HOME',Path(__file__).resolve().parents[4]))
    library=home/'SpinalSoc'
    if not (library/'build.sbt').is_file():raise ValueError('set RVW_HOME to a checkout with SpinalSoc')
    obj=json.loads((library/'examples/soc.json').read_text());obj['name']=name;obj['platform']['name']=name
    spec=json.loads((library/'examples/compose.json').read_text());spec['core']['class']='board.ProjectCore'
    build=(library/'build.sbt').read_text().split('Compile / unmanagedSourceDirectories')[0]
    build+='\nCompile / unmanagedSourceDirectories += baseDirectory.value / "generated"\n'
    build+='Compile / unmanagedSourceDirectories += file('+json.dumps(str(library/'src/main/scala'))+')\n'
    files={'soc.json':dumps(obj),'compose.json':dumps(spec),'build.sbt':build,
        'project/build.properties':(library/'project/build.properties').read_text(),
        'src/main/scala/ProjectCore.scala':'package board\n/** Replace this idle wrapper with a Component with rvwsoc.CoreWrapper. */\nclass ProjectCore extends rvwsoc.IdleCore\n',
        'rvw.toml':f'[project]\nschema = "rvw.project/1"\nroot = "."\n[core]\nname = "{name}"\n',
        '.gitignore':'target/\nproject/target/\nproject/project/\ngenerated/\nrtl/\n',
        'README.md':f'# {name}\n\nThis scaffold elaborates a small APB3 SoC. ProjectCore is idle and does not\nexecute instructions. Replace it with your core wrapper. Add explicit device\nbinders and interrupt wires to the map and composition.\n\n```sh\nrvw soc compose compose.json --out generated\nsbt "runMain generated.Generate"\n```\n\nUse the workstation sbt lock for shared-machine builds. The build references\nSpinalSoc sources in RVW_HOME at scaffold time. Move that path when needed.\nAdd your C1 adapter to rvw.toml before using rvw regress. No simulation or\nverification result is claimed by scaffold generation.\n'}
    target.mkdir(parents=True)
    for name,text in files.items():
        p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    return dict(status='created',files=sorted(files),core='idle_wrapper')
