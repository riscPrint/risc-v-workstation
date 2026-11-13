"""Base, nested-extension and conditional clauses omitted by flat bullet imports."""
import hashlib
import re


def bullet_end(lines,start):
    """Keep attached NOTE paragraphs, which can contain scope restrictions."""
    end=start+1
    while end<len(lines) and not lines[end].startswith(('=', '- ', '** ')):
        if not lines[end]:
            following=end+1
            while following<len(lines) and not lines[following]:following+=1
            if following>=len(lines) or not lines[following].startswith('NOTE:'):
                break
            end=following+1
        else:
            end+=1
    return end


def additional(path,digest,lines):
    rows=[];profile=None;category=None;parent=None
    def add(start,end,suffix,extension='',kind='clause',requirement=None,**extra):
        text='\n'.join(lines[start:end]).rstrip()
        rows.append(dict(id=profile+'.'+suffix,profile=profile,extension=extension,kind=kind,
                         requirement=requirement or category,text=text,
                         obligation_sha256=hashlib.sha256(text.encode()).hexdigest(),
                         source=dict(path=str(path.resolve()),sha256=digest,line=start+1),**extra))
    for i,line in enumerate(lines):
        heading=re.fullmatch(r'=== (RV[AB]23[US]64) Profile',line)
        if heading:
            profile=heading[1];category=None;parent=None
        elif line.startswith(('== ','=== ')):
            profile=None;category=None;parent=None
        if not profile:
            continue
        if line.startswith('==== '):
            parent=None
            category='mandatory' if 'Mandatory' in line else 'optional' if 'Optional' in line else None
            if 'Mandatory Base' in line:
                start=i+1
                while start<len(lines) and not lines[start]:start+=1
                end=start
                while end<len(lines) and not lines[end].startswith('==='):end+=1
                add(start,end,'base',kind='base',requirement='mandatory')
        if line.startswith('*Sha* comprises'):
            parent='sha'
        nested=re.match(r'\*\* \*([A-Za-z][A-Za-z0-9]*)\* ',line)
        if nested and parent:
            extension=nested[1].lower()
            add(i,bullet_end(lines,i),extension,extension,'extension',parent_extension=parent)
        if line.startswith('- If the hypervisor extension is implemented and pointer masking'):
            add(i,bullet_end(lines,i),'hypervisor_pointer_mask',requirement='conditional',
                when_any=[['h','ssnpm'],['sha','ssnpm']])
    return rows


def expand_sha(rows,implemented):
    """A selected optional Sha retains the constituents in its pinned definition."""
    definitions={row['extension']:row for row in rows if row.get('parent_extension')=='sha'}
    result=list(rows)
    for parent in rows:
        if parent.get('extension')!='sha':continue
        profile=parent['profile']
        existing={row['extension'] for row in result if row['profile']==profile}
        if not definitions and 'sha' in implemented:
            raise ValueError('selected Sha needs its pinned constituent definition')
        for extension,definition in definitions.items():
            if extension not in existing:
                row=dict(definition,id=profile+'.'+extension,profile=profile,
                         requirement='conditional',when_any=[['sha']],definition_from=definition['profile'])
                result.append(row)
    return result


def active(row,implemented):
    if row['requirement']=='conditional':
        return any(all(extension in implemented for extension in branch) for branch in row['when_any'])
    return row['requirement']=='mandatory' or row['extension'] in implemented


def declared(row,implemented,xlen,plan):
    if row.get('kind') in ('base','clause'):
        return xlen==64 and plan.get('declarations',{}).get(row['id']) is True
    return xlen==64 and row['extension'] in implemented


def catalogs(report):
    """Export source-bound catalogs. Missing checker mappings remain explicit."""
    result={}
    for profile in report['profiles'].values():
        for row in profile['obligations']:
            source=row['source'];key=source['sha256']
            catalog=result.setdefault(key,dict(schema='rvw.spec-obligations/1',source=source,obligations=[],unmapped_checkers=[]))
            entry=dict(id=row['id'],text=row['text'],checkers=row['checkers'],tests=[test['path'] for test in row['tests']])
            catalog['obligations'].append(entry)
            if not row['checkers']:catalog['unmapped_checkers'].append(row['id'])
    return result


def source_index(report):
    """Store source spans and hashes without copying specification prose."""
    from pathlib import Path
    sources={};rows=[]
    for profile in report['profiles'].values():
        for row in profile['obligations']:
            source=row['source'];digest=source['sha256']
            sources[digest]=dict(name=Path(source['path']).name,sha256=digest,
                                 **{key:source[key] for key in ('url','revision') if key in source})
            entry={key:row[key] for key in ('id','profile','extension','requirement','obligation_sha256')}
            entry.update(kind=row.get('kind','extension'),source_sha256=digest,
                         line=source['line'],end_line=source['line']+len(row['text'].splitlines())-1,
                         checkers=row['checkers'],tests=[test['path'] for test in row['tests']])
            entry.update({key:row[key] for key in ('parent_extension','when_any','inherited_from','definition_from') if key in row})
            rows.append(entry)
    return dict(schema='rvw.profile-source-index/1',sources=list(sources.values()),obligations=rows,
                limits=['Source-span inventory, not execution or profile compliance.',
                        'Assign and review checker and test mappings before catalog adoption.'])


def materialize(index,root):
    """Verify pinned source spans before producing reviewed-catalog inputs."""
    from pathlib import Path
    if index.get('schema')!='rvw.profile-source-index/1':
        raise ValueError('expected rvw.profile-source-index/1')
    documents={}
    for source in index['sources']:
        name=source['name']
        if Path(name).name!=name:
            raise ValueError('source index needs plain file names')
        raw=(Path(root)/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=source['sha256']:
            raise ValueError('profile source index hash differs')
        documents[source['sha256']]=raw.decode().splitlines()
    result={};seen=set()
    for row in index['obligations']:
        if row['id'] in seen:
            raise ValueError('duplicate indexed obligation')
        seen.add(row['id'])
        lines=documents[row['source_sha256']]
        first,last=row['line'],row['end_line']
        if type(first) is not int or type(last) is not int or not 1<=first<=last<=len(lines):
            raise ValueError('invalid profile source span')
        text='\n'.join(lines[first-1:last]).rstrip()
        if hashlib.sha256(text.encode()).hexdigest()!=row['obligation_sha256']:
            raise ValueError('indexed obligation text hash differs')
        catalog=result.setdefault(row['source_sha256'],dict(schema='rvw.spec-obligations/1',obligations=[],unmapped_checkers=[]))
        catalog['obligations'].append(dict(id=row['id'],text=text,checkers=row['checkers'],tests=row['tests']))
        if not row['checkers']:catalog['unmapped_checkers'].append(row['id'])
    return result
