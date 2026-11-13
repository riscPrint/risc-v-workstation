"""Append sampled, per-property progress without assigning proof verdicts."""
from pathlib import Path
import json
import re
import threading
import time
from rvw.common.proc import run_group

_WRITE_LOCK = threading.Lock()


def metrics(text):
    depths=[int(x) for x in re.findall(r'(?:Checking assertions in step|Checking cover reachability in step|Reached depth)\s+(\d+)',text)]
    frames=[int(x) for x in re.findall(r'\bFrame[ =]+(\d+)',text)]
    return {'depth_reached':max(depths) if depths else None,
            'depth_meaning':'started_solver_step' if depths else 'not_reported',
            'pdr_frame':max(frames) if frames else None}


def memory(pid):
    try:
        r=run_group(['ps','-axo','pgid=,rss='],capture=True,timeout=1)
        rows=[line.split() for line in (r.stdout or '').splitlines()]
        sizes=[int(row[1])*1024 for row in rows if len(row)==2 and int(row[0])==pid]
        return sum(sizes) if sizes else None
    except (OSError,ValueError):
        return None


class Progress:
    def __init__(self,path,property_id,engine,directory,interval=1):
        self.path=Path(path);self.property_id=property_id;self.engine=engine
        self.directory=Path(directory);self.interval=interval;self.pid=None
        self.began=time.monotonic();self.event=threading.Event();self.thread=None
        self.sequence=0

    def emit(self,event,status=None):
        text=''
        for pattern in ('problem/logfile.txt','problem/engine_*/logfile.txt','engine.log'):
            for p in self.directory.glob(pattern):
                try:text+='\n'+p.read_text(errors='replace')
                except OSError:pass
        record={'schema':'rvw.formal-progress/1','event':event,'property_id':self.property_id,
                'engine':self.engine,'sequence':self.sequence,'elapsed_s':time.monotonic()-self.began,
                'memory_bytes':memory(self.pid) if self.pid is not None else None,
                'memory_scope':'sampled_process_group_rss','native_status':status,
                'status_scope':'native_engine_observation','property_scope':'manifest_problem',**metrics(text)}
        self.sequence+=1
        with _WRITE_LOCK:
            with self.path.open('a') as f:f.write(json.dumps(record)+'\n')

    def start(self,pid):
        self.pid=pid;self.emit('started')
        def sample():
            while not self.event.wait(self.interval):self.emit('sample')
        self.thread=threading.Thread(target=sample,daemon=True);self.thread.start()

    def stop(self,status):
        self.event.set()
        if self.thread is not None:self.thread.join()
        self.emit('finished',status)
