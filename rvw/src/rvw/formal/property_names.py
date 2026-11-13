"""Expand selected zero-argument named property references within their module."""
import re

from .sva import _group
from .temporal import Unsupported,unwrap


def expand(source,select):
    from .sva_defaults import expand as expand_defaults
    source = expand_defaults(source)
    text=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m[0]),source,flags=re.S)
    edits=[]
    for module in re.finditer(r'\bmodule\b.*?\bendmodule\b',text,re.S):
        properties={}
        for decl in re.finditer(r'\bproperty\s+(\w+)\s*;(.*?)\bendproperty\b',module[0],re.S):
            if decl[1] in properties:
                raise Unsupported('duplicate_property',decl[1])
            properties[decl[1]]=(decl[2].strip().removesuffix(';').strip(),decl)
        used=set()
        for statement in re.finditer(r'\b(assert|assume|cover)\s+property\s*\(',module[0]):
            start=module.start()+statement.end()
            body,end=_group(text,start-1)
            names=[]
            while unwrap(body) in properties:
                name=unwrap(body)
                if name in names:
                    raise Unsupported('recursive_property',name)
                names.append(name)
                body=properties[name][0]
            if names and select(body):
                edits.append((start,end-1,body))
                used.update(names)
        for name in used:
            decl=properties[name][1]
            edits.append((module.start()+decl.start(),module.start()+decl.end(),''))
    for start,end,replacement in sorted(edits,reverse=True):
        source=source[:start]+replacement+source[end:]
    return source
