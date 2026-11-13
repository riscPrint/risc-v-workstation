"""Explicit trusted behavioral models for conditional equivalence runs."""
import json
from pathlib import Path
from .snapshot import digest


def load(path, out):
    path=Path(path).resolve()
    if path.is_relative_to(out):raise ValueError('blackbox contract must be outside --out')
    raw=path.read_bytes();plan=json.loads(raw)
    obligations=plan.get('obligations')
    if plan.get('schema')!='rvw.equiv-blackbox/1' or not isinstance(obligations,list) or not obligations or not all(isinstance(x,str) and x.strip() for x in obligations):
        raise ValueError('blackbox contract needs rvw.equiv-blackbox/1 and explicit obligations')
    names=plan['models']
    if not isinstance(names,list) or not names or not all(isinstance(n,str) for n in names):
        raise ValueError('blackbox contract needs model source paths')
    models=[(path.parent/name).resolve() for name in names]
    if any(p.is_relative_to(out) or not p.is_file() for p in models):
        raise ValueError('blackbox models must be existing files outside --out')
    target=out/'blackbox-contract.json';target.write_bytes(raw)
    return [str(p) for p in models], {'schema':'rvw.equiv-blackbox/1','manifest_sha256':digest(target),
        'models':[{'source':str(p),'sha256':digest(p)} for p in models],
        'obligations':plan['obligations'],
        'scope':'trusted behavioral models; correspondence to physical blackboxes is not proved'}
