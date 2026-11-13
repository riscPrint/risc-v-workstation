"""Scripted evidence solver over the external runner's MCP transport."""
import json
import os
import anyio
from mcp import ClientSession
from mcp.client.sse import sse_client
from .solver import solve


async def main():
    async with sse_client(os.environ['RVW_BENCH_MCP_URL'],
                          headers={'Authorization': 'Bearer ' + os.environ['RVW_BENCH_MCP_TOKEN']}) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            async def call(tool, arguments):
                response = await session.call_tool(tool, arguments)
                if getattr(response, 'is_error', getattr(response, 'isError', False)):
                    raise RuntimeError(response.content[0].text)
                return json.loads(response.content[0].text)
            task = await call('bench_inspect', {})
            result = await solve(call, task['steps'], max_calls=task['max_calls'], budget_s=task['budget_s'])
            await call('bench_finish', {'claimed_fix': False, 'outcome': result['status'],
                                        'timed_out': result['timed_out']})


if __name__ == '__main__':
    anyio.run(main)
