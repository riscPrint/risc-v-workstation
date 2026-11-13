"""Small editable SoC project with a deliberate non-executing core wrapper."""
import json
import os
import re
from pathlib import Path
from .model import ident,dumps


def new(name,out,project=None):
    ident(name)
    from rvw.common.project import load_project
    project = load_project(project)
    core_map = project.root/'rvw/core-map.json' if project else None
    mapped = json.loads(core_map.read_text()) if core_map and core_map.is_file() else None
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
    checker_names = ['SpinalCompat.scala','ProtocolChecks.scala','AxiReadChecks.scala','AxiWriteChecks.scala',
                     'TileLinkProbeChecks.scala','BusAssertions.scala']
    build += 'Compile / unmanagedSources ++= Seq('+','.join(json.dumps(n) for n in checker_names)+').map(file('+json.dumps(str(home/'SpinalChecks/src/main/scala/spinalchecks'))+') / _)\n'
    files={'soc.json':dumps(obj),'compose.json':dumps(spec),'build.sbt':build,
        'project/build.properties':(library/'project/build.properties').read_text(),
        'src/main/scala/ProjectCore.scala':'package board\n/** Replace this idle wrapper with a Component with rvwsoc.CoreWrapper. */\nclass ProjectCore extends rvwsoc.IdleCore\n',
        'rvw.toml':f'[project]\nschema = "rvw.project/1"\nroot = "."\n[core]\nname = "{name}"\n',
        '.gitignore':'target/\nproject/target/\nproject/project/\ngenerated/\nrtl/\n',
        'README.md':f'# {name}\n\nThis scaffold elaborates a small APB3 SoC. ProjectCore is idle and does not\nexecute instructions. Replace it with your core wrapper. Add explicit device\nbinders and interrupt wires to the map and composition.\n\n```sh\nrvw soc compose compose.json --out generated\nsbt "runMain generated.Generate"\n```\n\nUse the workstation sbt lock for shared-machine builds. The build references\nSpinalSoc sources in RVW_HOME at scaffold time. Move that path when needed.\nAdd your C1 adapter to rvw.toml before using rvw regress. No simulation or\nverification result is claimed by scaffold generation.\n'}
    core_kind = 'idle_wrapper'
    if mapped:
        from rvw.init.soc_scaffold import wrapper
        files['src/main/scala/ProjectCore.scala'] = wrapper(mapped)
        spec['core'] = dict(**{'class':'rvwproject.RvwProjectCore'}, bus='simple')
        if mapped.get('rvfi'):
            from rvw.init.mapped import RVFI_FIELDS
            spec['core']['exports'] = ['rvfi_'+f for f in RVFI_FIELDS]
        spec['reset'] = 'async_high'
        obj['regions'][0]['base'] = mapped['ram']['base']
        obj['regions'][0]['size'] = mapped['ram']['size']
        obj['platform'] = dict(name=mapped['core'],xlen=32,isa=mapped['isa'],
                               reset_pc=mapped['reset_pc'],aligned_mem=True,privilege_modes='M')
        files['soc.json'] = dumps(obj)
        files['compose.json'] = dumps(spec)
        adapter_build = (project.root/'rvw/build.sbt').read_text()
        ids = re.findall(r'ProjectRef\(coreSource, "([^"]+)"\)', adapter_build)
        if len(ids) != 1:
            raise ValueError('mapped SoC needs one coreSource ProjectRef in rvw/build.sbt')
        files['build.sbt'] += '\nlazy val root = (project in file(".")).dependsOn(ProjectRef(file('+json.dumps(str(project.root))+'), '+json.dumps(ids[0])+'))\n'
        files['README.md'] = '# '+name+'\n\nMapped CPU wrapper over SimpleCpuBus. Review the generated map.\nRun rvw soc compose compose.json --out generated. Then run sbt "runMain generated.Generate".\nNo native execution is claimed by generation.\n'
        core_kind = 'mapped_wrapper'
    target.mkdir(parents=True)
    for name,text in files.items():
        p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    return dict(status='created',files=sorted(files),core=core_kind)
