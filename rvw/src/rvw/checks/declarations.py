"""Unbound check declarations for review in a new core project."""
import re


def ports(kind):
    from rvw.formal.micro_checks import PORTS
    if kind in PORTS:
        return sorted({'clk','reset',*PORTS[kind]})
    from rvw.formal.invariants import render
    header=render(kind,4,8).split(');',1)[0]
    names={'clk','reset'}
    for group in re.split(r'\binput\s+',header)[1:]:
        group=re.sub(r'\[[^]]*\]','',group)
        for item in group.split(','):
            name=item.strip().rstrip(')').strip()
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):names.add(name)
    return sorted(names)


def template(kind):
    return dict(id=kind+'_instance',kind=kind,width=4,entries=8,
                ports={name:'REPLACE_'+name for name in ports(kind)})


def scaffold():
    from rvw.formal.micro_checks import PORTS
    from rvw.formal.ooo_checks import PORTS as OOO
    return dict(schema='rvw.micro-checks/1',top='REPLACE_TOP',rules=[template(k) for k in dict.fromkeys([*PORTS,*OOO])])
