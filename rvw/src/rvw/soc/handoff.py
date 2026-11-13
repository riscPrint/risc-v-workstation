"""Capture implementation inputs with design-database content bindings."""
import hashlib
import json
from pathlib import Path

from rvw.query.db import DesignDB, QueryError, SCHEMA
from rvw.lint.sdc import analyze
from .model import dumps


def rows(db, table):
    cursor = db.conn.execute(f'SELECT * FROM {table}')
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, r)) for r in cursor]


def export(db_path, out, settings=None):
    target=Path(out)
    if target.exists():
        raise ValueError('handoff output must be new')
    db=DesignDB(db_path)
    try:
        if db.schema!=SCHEMA:
            raise ValueError('handoff requires the current design database schema')
        rtl={r['path'] for r in rows(db,'rtl_files')}
        if not rtl:
            raise ValueError('database has no RTL files')
        inputs=rows(db,'input_files')
        bound={r['path']:r for r in inputs}
        if rtl-bound.keys():
            raise ValueError('RTL files have no captured input binding')
        captured=[]
        for index,item in enumerate(sorted(inputs,key=lambda r:r['path'])):
            src=Path(item['resolved'] or item['path'])
            if not src.is_absolute():
                src=Path(db_path).resolve().parent/src
            cap=db.capture.file(src)
            if cap.sha256!=item['sha256']:
                raise ValueError('input differs from database capture: '+str(src))
            dest=f'inputs/{index:04d}/{src.name}'
            captured.append((cap, dest, item['path']))
        settings = settings or {}
        timing=analyze(db,settings.get('sdc',{}),settings.get('intent',{}))
        inventories={name:rows(db,name) for name in ('clock_domains','clock_frequencies','memories','mem_ports','components','blackboxes')}
        manifest=dict(schema='rvw.soc-handoff/1',status='exported',design_meta=db.meta,
                      database_sha256=db.input.sha256, validation_scope='captured inputs and logical timing intent only',
                      files=[dict(source=source,path=dest,sha256=cap.sha256,rtl=source in rtl) for cap,dest,source in captured],
                      unresolved_blackboxes=inventories['blackboxes'],
                      parameters_scope='database metadata and blackbox generics; ordinary Scala constructor parameters are not captured',
                      sdc_findings=timing['findings'], input_capture=db.capture.record())
        target.mkdir(parents=True)
        for cap,dest,source in captured:
            path=target/dest
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(cap.copy.read_bytes())
        (target/'files.f').write_text(''.join(dest+'\n' for _,dest,source in captured if source in rtl))
        (target/'constraints.sdc').write_text(timing['sdc'])
        for name,data in inventories.items():
            (target/(name+'.json')).write_text(dumps(data))
        (target/'handoff.json').write_text(dumps(manifest))
        return manifest
    finally:
        db.close()
