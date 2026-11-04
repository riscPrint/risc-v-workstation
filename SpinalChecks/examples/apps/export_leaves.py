"""Export two leaf contracts from supplied generated RTL. No elaboration or core edits."""
import re,json,hashlib
from pathlib import Path
import argparse
p=argparse.ArgumentParser()
p.add_argument('--vex-rtl', required=True, type=Path)
p.add_argument('--boom-rtl', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
args=p.parse_args()
base=args.out; base.mkdir(parents=True, exist_ok=False)
configs=[('vex',args.vex_rtl,'StreamFifo','io_occupancy && io_availability'),('boom',args.boom_rtl,'ForwardingAgeLogic','io_found != (io_matches != 0)')]
for tag,path,module,target in configs:
 text=path.read_text(); m=re.search(r'^module '+module+r'\s*\(.*?^endmodule',text,re.M|re.S)
 assert m
 rtl=m[0]+'\n';(base/(tag+'.sv')).write_text(rtl)
 ports={}
 for direction,width,name in re.findall(r'\b(input|output)\s+(?:wire|reg)\s*(\[\d+:\d+\])?\s*(\w+)',rtl.split(');')[0]):
  w=1
  if width:
   high,low=map(int,re.findall(r'\d+',width));w=high-low+1
  ports[name]=dict(direction=direction,width=w)
 plan=dict(schema='rvw.formal-apps/1',top=module,clock='clk',reset='reset',ports=ports,verilog=[tag+'.sv'],properties=[dict(id=tag+'_invariant',kind='unr',target=target,requirement_ids=[tag+'_leaf_contract'])])
 (base/(tag+'.json')).write_text(json.dumps(plan,indent=2)+'\n')
 print(tag, 'full_rtl_sha256',hashlib.sha256(path.read_bytes()).hexdigest(),'leaf_sha256',hashlib.sha256(rtl.encode()).hexdigest())
