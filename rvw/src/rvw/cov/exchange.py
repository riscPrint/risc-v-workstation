"""Counter interchange. The UCIS profile stores native counter kinds as metadata."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from . import captured
from rvw.common.proc import run_group

NS='UCIS'
ET.register_namespace('',NS)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'))


def normalized(report):
    schema=report.get('schema')
    rows=[]
    if schema=='rvw.coverage/1':
        context={k:report.get(k) for k in ('schema','point_universe','source_root','source_revision','sources')}
        context['native_contexts'] = sorted({canonical({key:run.get(key) for key in ('core','config','source','tools')})
            for test in report.get('tests',{}).values() if (run:=test.get('run'))})
        for point in report['points']:
            rows.append({'id':point['id'],'kind':'code:'+point['fields'].get('t','unknown'),
                         'count':point['count'],'metadata':{k:v for k,v in point.items() if k not in ('count','tests')}})
    elif schema=='rvw.functional-coverage/1':
        context={k:report.get(k) for k in ('schema','config','config_sha256')}
        context['trace_contexts'] = sorted({canonical({
            'header':{k:v for k,v in trace['header'].items() if k not in ('elf','elf_sha256','seed')},
            'platform':trace.get('platform'),'address_convention':trace.get('address_convention')})
            for trace in report.get('traces',{}).values()})
        for name,group in report['groups'].items():
            hits={canonical(h['bin']):(h['bin'],h['count']) for h in group['hits']}
            for value in group['holes']:
                hits.setdefault(canonical(value),(value,0))
            for value,count in hits.values():
                rows.append({'id':name+':'+canonical(value),'kind':'functional', 'count':count,
                             'metadata':{'group':name,'bin':value,'fields':group['fields'],
                                         'classifications':group.get('classifications',[])}})
    elif schema=='rvw.assertion-counters/1':
        context={k:report.get(k) for k in ('schema','design_sha256','properties')}
        for prop in report['properties']:
            for kind,count in prop['counts'].items():
                if kind not in ('pass','fail','cover','vacuous','disabled','attempt','active','peak_active'):
                    raise ValueError('unsupported assertion counter')
                rows.append({'id':prop['id']+':'+kind,'kind':'assertion:'+kind,'count':count,
                             'metadata':{k:v for k,v in prop.items() if k!='counts'}})
        context['properties']=[{k:v for k,v in p.items() if k!='counts'} for p in report['properties']]
    elif schema=='rvw.coverage-exchange/1':
        return validate(report)
    else:
        raise ValueError('unsupported interchange input schema')
    value={'schema':'rvw.coverage-exchange/1','context':context,'rows':sorted(rows,key=lambda r:r['id']),
           'status':'reported','proof_exclusions_verified':False}
    return validate(value)


def validate(value):
    if value.get('schema')!='rvw.coverage-exchange/1' or not value.get('rows'):
        raise ValueError('expected nonempty rvw.coverage-exchange/1')
    ids=[]
    for row in value['rows']:
        if set(row)!={'id','kind','count','metadata'} or not row['id'] or type(row['count']) is not int or row['count']<0:
            raise ValueError('invalid coverage exchange counter')
        ids.append(row['id'])
    if len(set(ids))!=len(ids):
        raise ValueError('duplicate exchange bin ID')
    return value


def export_ucis(report):
    value=normalized(report)
    def element(parent,tag,**attrs):
        return ET.SubElement(parent,'{'+NS+'}'+tag,{k:str(v) for k,v in attrs.items()})
    root=ET.Element('{'+NS+'}UCIS',{'ucisVersion':'1.0','writtenBy':'rvw','writtenTime':'1970-01-01T00:00:00Z'})
    element(root,'sourceFiles',fileName='rvw-counter-profile',id=1)
    element(root,'historyNodes',historyNodeId=0,logicalName='imported-counters',testStatus='false',date='1970-01-01T00:00:00Z',
            toolCategory='coverage',ucisVersion='1.0',vendorId='rvw',vendorTool='rvw',vendorToolVersion='1')
    instance=element(root,'instanceCoverages',name='rvw',key='rvw')
    element(instance,'id',file=1,line=1,inlineCount=1)
    coverage=element(instance,'covergroupCoverage')
    group=element(coverage,'cgInstance',name='rvw-counters',key='rvw-counters')
    element(group,'options')
    group_id=element(group,'cgId',cgName='rvw-counters',moduleName='rvw')
    for name in ('cginstSourceId','cgSourceId'):
        element(group_id,name,file=1,line=1,inlineCount=1)
    for index,row in enumerate(value['rows']):
        point=element(group,'coverpoint',name=row['id'],key=str(index))
        element(point,'options')
        bin_=element(point,'coverpointBin',name=row['id'],key=str(index),type='bins')
        range_=element(bin_,'range',**{'from':0,'to':0})
        element(range_,'contents',coverageCount=row['count'])
        element(bin_,'userAttr',key='rvw.counter',type='str').text=canonical({k:v for k,v in row.items() if k!='count'})
    element(instance,'userAttr',key='rvw.profile',type='str').text='rvw-counter-profile/1'
    element(instance,'userAttr',key='rvw.context',type='str').text=canonical(value['context'])
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def import_ucis(content):
    if b'<!DOCTYPE' in content or b'<!ENTITY' in content:
        raise ValueError('XML entities are outside the declared UCIS profile')
    try:
        root=ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError('invalid UCIS XML: '+str(exc)) from exc
    q=lambda name:'{'+NS+'}'+name
    if root.tag!=q('UCIS') or root.get('ucisVersion')!='1.0':
        raise ValueError('expected UCIS 1.0 namespace')
    instances=root.findall(q('instanceCoverages'))
    if len(instances)!=1:
        raise ValueError('counter profile requires one logical instance')
    instance=instances[0]
    attrs={a.get('key'):a.text for a in instance.findall(q('userAttr'))}
    if attrs.get('rvw.profile')!='rvw-counter-profile/1':
        raise ValueError('unsupported UCIS profile; native metric import is not implemented')
    rows=[]
    for point in instance.findall('.//'+q('coverpoint')):
        bins=point.findall(q('coverpointBin'))
        if len(bins)!=1:
            raise ValueError('counter profile needs one bin per point')
        bin_=bins[0];metadata=bin_.find(q('userAttr'))
        ranges=bin_.findall(q('range'))
        if metadata is None or metadata.get('key')!='rvw.counter' or len(ranges)!=1 or ranges[0].get('from')!='0' or ranges[0].get('to')!='0':
            raise ValueError('unsupported counter metadata or range')
        contents=ranges[0].find(q('contents'))
        row=json.loads(metadata.text);row['count']=int(contents.attrib['coverageCount'])
        if point.get('name')!=row['id'] or bin_.get('name')!=row['id']:
            raise ValueError('counter identity differs from metadata')
        rows.append(row)
    result=validate({'schema':'rvw.coverage-exchange/1','context':json.loads(attrs['rvw.context']),
                     'rows':sorted(rows,key=lambda r:r['id']),'status':'reported','proof_exclusions_verified':False})
    # Reject fields outside this declared profile rather than silently losing them.
    def structure(node):
        return [node.tag,dict(sorted(node.attrib.items())),(node.text or '').strip(),[structure(c) for c in node]]
    if structure(root)!=structure(ET.fromstring(export_ucis(result))):
        raise ValueError('unsupported UCIS structure or attributes')
    return result


def merge_exchanges(reports):
    reports=[normalized(r) for r in reports]
    if not reports:
        raise ValueError('no exchange inputs')
    first=json.loads(canonical(reports[0]))
    signature=lambda r:canonical([r['context'],[{k:v for k,v in row.items() if k!='count'} for row in r['rows']]])
    identity=signature(first)
    for other in reports[1:]:
        if signature(other)!=identity:
            raise ValueError('incompatible coverage source, bin semantics or exclusions')
        for left,right in zip(first['rows'],other['rows']):
            left['count']+=right['count']
    return first


def dat_bytes(report):
    if report.get('schema')!='rvw.coverage/1' or not report.get('points'):
        raise ValueError('native export requires a code coverage database')
    lines=['# SystemC::Coverage-3']
    seen=set()
    for point in report['points']:
        key=point['key'];count=point['count']
        if '\n' in key or '\r' in key or point['id']!=sha256(key.encode()).hexdigest() or point['id'] in seen or type(count) is not int or count<0:
            raise ValueError('invalid native coverage point')
        seen.add(point['id']);lines.append(f"C '{key}' {count}")
    return ('\n'.join(lines)+'\n').encode()


@captured.command
def exchange(database,destination,format='ucis'):
    source=Path(database);target=Path(destination)
    if source.resolve()==target.resolve():
        raise ValueError('export must not overwrite input')
    sidecar=Path(str(target)+'.rvw.json')
    if sidecar.resolve()==source.resolve():
        raise ValueError('metadata sidecar must not overwrite input')
    raw=captured.read_bytes(source)
    if format=='import-ucis':
        result=import_ucis(raw);target.write_text(json.dumps(result,indent=2)+'\n')
    else:
        report=json.loads(raw)
        if format=='ucis':
            target.write_bytes(export_ucis(report))
        elif format=='dat':
            target.write_bytes(dat_bytes(report))
        elif format=='lcov':
            tool=captured.tool('verilator_coverage')
            with tempfile.TemporaryDirectory(prefix='rvw-lcov-') as directory:
                dat=Path(directory)/'coverage.dat';dat.write_bytes(dat_bytes(report))
                output=Path(directory)/'coverage.info'
                ran=run_group([str(tool.path),'--write-info',str(output),str(dat)],timeout=60,capture=True)
                if ran.returncode or ran.timed_out or not output.is_file():
                    raise ValueError('native LCOV export failed: '+str(ran.stderr))
                target.write_bytes(output.read_bytes())
        else:
            raise ValueError('unsupported export format')
        result=normalized(report)
    sidecar.write_text(json.dumps(result,indent=2)+'\n')
    return {'metadata':str(sidecar),'metadata_sha256':sha256(sidecar.read_bytes()).hexdigest(),
            'schema':'rvw.coverage-export/1','status':'reported','format':format,'destination':str(target),
            'sha256':sha256(target.read_bytes()).hexdigest(),'bins':len(result['rows']),
            'notes':['Counter transport grants no proof exclusion or C4 acceptance.']}
