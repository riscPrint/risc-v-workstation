"""Small exact-schema design databases for lint tests. Not extracted RTL evidence."""
import re
import sqlite3
from pathlib import Path


SCHEMA = Path(__file__).parents[2] / 'SpinalDB/spinaldb/src/main/scala/spinaldb/Schema.scala'


class Builder:
    def __init__(self, path, top='Top'):
        self.path = Path(path)
        self.c = sqlite3.connect(self.path)
        for a, b in re.findall(r'"""(CREATE TABLE.*?)"""|"(CREATE TABLE[^"\n]*)"', SCHEMA.read_text(), re.S):
            self.c.execute(re.sub(r'\n\s*\|', '\n', a or b))
        self.c.execute("INSERT INTO meta VALUES('schema','rvw.designdb/20')")
        self.c.execute("INSERT INTO meta VALUES('toplevel',?)", (top,))
        self.c.execute("INSERT INTO files VALUES(1,'Top.scala')")
        self.c.execute("INSERT INTO components(id,path,name,depth,class_name) VALUES(1,'',?,0,'Top')", (top,))
        self.ids, self.next, self.comps = {}, 1, {'': 1}
        self.assign_id = 0

    def component(self, path, cls, parent=''):
        cid = len(self.comps) + 1
        self.comps[path] = cid
        self.c.execute('INSERT INTO components(id,parent_id,path,name,depth,class_name) VALUES(?,?,?,?,?,?)',
                       (cid, self.comps[parent], path, path.split('.')[-1], path.count('.') + 1, cls))
        return cid

    def domain(self, i, clock='clk', reset=None, kind='BOOT', high='true', clock_key=None, edge='RISING',
               enable=None):
        self.c.execute('INSERT INTO clock_domains(id,clock,reset,reset_kind,reset_active_high,clock_edge,clock_key,'
                       'reset_key,clock_enable,clock_enable_key) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (i, clock, reset, kind if reset or kind != 'BOOT' else 'BOOT', high if reset else None, edge,
                        clock_key or (clock + ':Bool' if clock else None), reset + ':Bool' if reset else None,
                        enable, enable + ':Bool' if enable else None))

    def sig(self, path, kind='wire', width=1, domain=None, init='0', direction=None, comp='', role=None,
            type_=None, tags=None, pruned=0, name=None):
        i = self.next
        self.next += 1
        self.ids[path] = i
        self.c.execute('INSERT INTO signals(id,component_id,name,path,kind,direction,type,width,clock_domain_id,'
                       'reset_value,clock_role,pruned,tags,file_id,line) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)',
                       (i, self.comps[comp], name or path.split('.')[-1], path, kind, direction,
                        type_ or ('Bool' if width == 1 else 'Bits'), width, domain,
                        init if kind == 'reg' else None, role, pruned, tags, i))
        return i

    def reg(self, path, domain, width=1, **kw):
        return self.sig(path, 'reg', width, domain, **kw)

    def edge(self, a, b, kind='data'):
        self.c.execute('INSERT OR IGNORE INTO edges VALUES(?,?,?)', (self.ids[a], self.ids[b], kind))

    def chain(self, *paths, kind='data'):
        for a, b in zip(paths, paths[1:]):
            self.edge(a, b, kind)

    def assign(self, target, key, kind='data', cond=None, comp=None, source=None):
        self.assign_id += 1
        cid = self.comps[comp] if comp is not None else self.c.execute(
            'SELECT component_id FROM signals WHERE id=?', (self.ids[target],)).fetchone()[0]
        self.c.execute('INSERT INTO assignments(id,target_id,component_id,kind,key,source,cond_id,seq) VALUES(?,?,?,?,?,?,?,?)',
                       (self.assign_id, self.ids[target], cid, kind, key, source, cond, self.assign_id))

    def done(self):
        self.c.commit()
        self.c.close()
        return self.path
