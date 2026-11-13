"""Self-contained gem5 adapter export. Does not run or build gem5."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from rvw.ooo.project import configuration


def export(description,out):
    raw=Path(description).read_bytes();data=json.loads(raw)
    if data.get('schema')!='rvw.arch-core/1' or data.get('kind')!='o3':
        raise ValueError('shared O3 project description required')
    own=asdict(configuration(data))
    source=Path(__file__).resolve().parents[4]/'Arch/model.py'
    p=Path(out);p.mkdir(parents=True,exist_ok=False)
    (p/'core.json').write_bytes(raw)
    (p/'ooo.json').write_text(json.dumps(own,indent=2)+'\n')
    (p/'model.py').write_bytes(source.read_bytes())
    report=dict(schema='rvw.gem5-export/1',status='reported',
                description_sha256=sha256(raw).hexdigest(),
                adapter_sha256=sha256(source.read_bytes()).hexdigest(),
                gem5_version='v25.1.0.1',
                command='gem5.opt --outdir=run model.py --description core.json PROGRAM.elf',
                shared=dict(cpu=data['cpu'],issue_entries=own['issue_entries']),
                limits=['files only; gem5 execution NOT RUN',
                        'shared dimensions do not establish timing parity',
                        'own latency policies and component internals differ from gem5 FU policies',
                        'requires the pinned workstation gem5 API and bare-metal ROI ELF contract'])
    (p/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
