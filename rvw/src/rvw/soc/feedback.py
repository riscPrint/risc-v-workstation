"""Keep external implementation claims distinct from workstation evidence."""
import hashlib
import json
from pathlib import Path
from rvw.query.db import DesignDB, QueryError
from .model import dumps, keys


def import_feedback(db_path, source, out):
    spec=json.loads(Path(source).read_text())
    keys(spec,{'schema','database_sha256','tool','scope','constraints','reports','findings'},
         {'schema','database_sha256','tool','scope','constraints','reports','findings'})
    if spec['schema']!='rvw.soc-feedback/1' or not all(isinstance(spec[k],str) and spec[k] for k in ('tool','scope')):
        raise ValueError('feedback needs schema, tool and scope')
    db=DesignDB(db_path)
    try:
        if spec['database_sha256']!=db.input.sha256:
            raise ValueError('feedback database identity differs')
        reports=[]
        for path in spec['reports']:
            cap=db.capture.file(Path(source).resolve().parent/path)
            reports.append(dict(path=path,sha256=cap.sha256,size=cap.size))
        findings=[]
        for item in spec['findings']:
            keys(item,{'kind','endpoint','message','report'}, {'kind','endpoint','message','report'})
            if item['kind'] not in ('timing','area','cdc','dft') or item['report'] not in spec['reports']:
                raise ValueError('finding needs a known kind and report')
            record=dict(item,claim='external',match='unmatched')
            try:
                signal=db.resolve_one(item['endpoint'])
                record.update(match='matched',rtl_path=signal.path,scala_file=signal.file,scala_line=signal.line)
            except QueryError as exc:
                record['diagnostic']=str(exc)
            findings.append(record)
        result=dict(schema='rvw.soc-feedback-links/1',status='imported_claims',database_sha256=db.input.sha256,
                    tool=spec['tool'],scope=spec['scope'],constraints=spec['constraints'],reports=reports,
                    findings=findings,input_capture=db.capture.record(),
                    note='External reports are imported claims. Endpoint resolution is not signoff validation.')
        with Path(out).open('x') as f: f.write(dumps(result))
        return result
    finally:
        db.close()
