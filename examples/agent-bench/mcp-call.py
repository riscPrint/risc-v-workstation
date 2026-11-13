import anyio,json,os,sys,time
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
 params=StdioServerParameters(command=sys.executable,args=['-m','rvw','mcp'],env=dict(os.environ))
 async with stdio_client(params) as streams:
  async with ClientSession(*streams) as session:
   await session.initialize()
   async def call(name,args):
    response=await session.call_tool(name,args)
    if response.is_error:raise RuntimeError(response.content[0].text)
    return json.loads(response.content[0].text)
   start=time.monotonic();records=[]
   with anyio.move_on_after(118) as scope:
    result=await call(sys.argv[1],json.loads(sys.argv[2]));records.append(result)
    while result.get('job_id') and result.get('status') in ('queued','running'):
     result=await call('job_status',{'job_id':result['job_id'],'wait_s':30});records.append(result)
   body={'wall_s':time.monotonic()-start,'timed_out':scope.cancel_called,'records':records}
   Path(sys.argv[3]).write_text(json.dumps(body,indent=2));print(json.dumps(body))
anyio.run(main)
