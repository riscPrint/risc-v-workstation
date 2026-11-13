"""Scripted baseline through the same external MCP connection as an agent CLI."""
import json
import os
import sys

import anyio
from mcp import ClientSession
from mcp.client.sse import sse_client
from rvw.agent_bench.engine import scripted


async def main():
    async with sse_client(os.environ['RVW_BENCH_MCP_URL'],
                          headers={'Authorization': 'Bearer ' + os.environ['RVW_BENCH_MCP_TOKEN']}) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            assert tools == {'bench_inspect', 'bench_diagnose', 'bench_reject', 'bench_patch', 'bench_finish', 'rvw_tools_search', 'rvw_tools_describe',
                             'job_status', 'job_log', 'job_cancel', 'job_list'}
            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                if getattr(result, 'is_error', getattr(result, 'isError', False)):
                    raise RuntimeError(result.content[0].text)
                return json.loads(result.content[0].text)
            if 'disconnect' in sys.argv:
                await call('bench_inspect', {})
                return
            if 'timeout' in sys.argv:
                await call('bench_inspect', {})
                await anyio.sleep_forever()
            await anyio.to_thread.run_sync(lambda: scripted(lambda n, a: anyio.from_thread.run(call, n, a),
                                                           careless='careless' in sys.argv))


if __name__ == '__main__':
    anyio.run(main)
