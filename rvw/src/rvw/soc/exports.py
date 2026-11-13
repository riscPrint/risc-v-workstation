"""Register-subset IP-XACT export, paired with the strict importer."""
from pathlib import Path
from xml.etree import ElementTree as ET
from .model import load
from rvw.csr.catalog import peripheral_registers

NS='http://www.accellera.org/XMLSchema/IPXACT/1685-2014'
ET.register_namespace('ipxact',NS)


def ipxact(obj):
    def element(parent,name,value=None):
        node=ET.SubElement(parent,'{'+NS+'}'+name)
        if value is not None: node.text=str(value)
        return node
    root=ET.Element('{'+NS+'}memoryMap')
    element(root,'name',obj['name'])
    element(root,'addressUnitBits',8)
    for region in obj['regions']:
        if not region['registers']: continue
        block=element(root,'addressBlock')
        for k,v in [('name',region['name']),('baseAddress',hex(region['base'])),('range',hex(region['size'])),('width',32),('usage','register')]: element(block,k,v)
        for r in peripheral_registers(region):
            reg=element(block,'register')
            for k,v in [('name',r['name']),('addressOffset',hex(r['offset'])),('size',r['width']),('access',{'r':'read-only','w':'write-only','rw':'read-write'}[r['access']])]:element(reg,k,v)
            field=element(reg,'field')
            element(field,'name',r['fields'][0]['name'])
            element(field,'bitOffset',r['fields'][0]['lsb']);element(field,'bitWidth',r['fields'][0]['width'])
            if r['reset'] is not None:
                reset=element(element(field,'resets'),'reset')
                element(reset,'value',hex(r['reset']));element(reset,'mask',hex((1<<r['width'])-1))
            if r['read_action']=='clear':element(field,'readAction','clear')
            if r['write_action']=='one_to_clear':element(field,'modifiedWriteValue','oneToClear')
    if not any(r['registers'] for r in obj['regions']):
        raise ValueError('IP-XACT register subset needs at least one register block')
    ET.indent(root)
    return ET.tostring(root,encoding='unicode')+'\n'


def export(source,out):
    text=ipxact(load(source))
    with Path(out).open('x') as f:f.write(text)
    return dict(status='exported',file=str(out),scope='IP-XACT 1685-2014 register memoryMap subset')
