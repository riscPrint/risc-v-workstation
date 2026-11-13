"""Ordered, explicit composition fragments without Scala inheritance."""
import hashlib
import json
from pathlib import Path
from .model import keys


def configuration(source):
    source=Path(source)
    local=json.loads(source.read_text())
    fragments=local.pop('fragments',[])
    if not isinstance(fragments,list) or any(not isinstance(f,str) for f in fragments):
        raise ValueError('fragments must be a list of JSON paths')
    merged={};hashes=[]
    def merge(fragment):
        for key,value in fragment.items():
            if key=='devices':
                if not isinstance(value,dict):raise ValueError('fragment devices must be a dictionary')
                merged.setdefault('devices',{}).update(value)
            else:merged[key]=value
    for name in fragments:
        path=source.resolve().parent/name
        raw=path.read_bytes()
        fragment=json.loads(raw)
        keys(fragment,{'devices','core','clock_hz','reset','domains'})
        hashes.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        merge(fragment)
    merge(local)
    return merged,hashes
