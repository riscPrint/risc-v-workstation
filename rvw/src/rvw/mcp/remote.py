"""Authenticated MCP SSE transport with one registry and job store per client."""
import hmac
from dataclasses import replace
from .registry import Registry, discover
from .jobs import JobManager
from .server import build_server

READ_ONLY = {'query_drivers', 'query_loads', 'query_path', 'query_where', 'evidence_query'}


class ClientRegistry(Registry):
    def __init__(self, *args, output=None, **kwargs):
        self.output = output
        super().__init__(*args, **kwargs)

    def call(self, name, arguments, *, dry_run=False):
        if self.project and arguments and (arguments.get('project', self.project) != self.project or arguments.get('core')):
            from .spec import ToolError
            raise ToolError('project is fixed by the client policy')
        from .paths import confine
        spec = self.tools.get(name)
        if spec is not None:
            arguments = confine(arguments, spec.input_schema, self.project, self.output)
        return super().call(name, arguments, dry_run=dry_run)


def remote_tool(spec):
    if spec.wants_job:
        return replace(spec, long=True)
    module, name = spec.handler.__module__, spec.handler.__qualname__
    if not name.isidentifier():
        if not module.startswith("rvw."):
            raise ValueError('remote tool needs an importable handler: ' + spec.name)
        def discovered(job, **arguments):
            from .worker import run_function
            return run_function(job, "rvw.mcp.execution", "run_discovered",
                                {"tool_name": spec.name, "arguments": arguments})
        return replace(spec, handler=discovered, long=True)
    def execute(job, **arguments):
        from .worker import run_function
        return run_function(job, module, name, arguments)
    return replace(spec, handler=execute, long=True)


class Remote:
    def __init__(self, clients, registry_factory=None, *, profile="all", workflow=None):
        from mcp.server.sse import SseServerTransport
        if not clients or any(not token for token in clients):
            raise ValueError('provide nonempty bearer tokens')
        self.clients = {}
        for token, policy in clients.items():
            allowed = set(policy.get('tools', []))
            if not allowed:
                raise ValueError('each client needs an explicit tool allowlist')
            if policy.get('read_only') and allowed - READ_ONLY:
                raise ValueError('read-only role contains a write or unknown tool')
            if registry_factory:
                registry = registry_factory(policy)
            else:
                tools, problems = discover()
                selected = [t for t in tools if t.name in allowed]
                if allowed - {t.name for t in selected}:
                    raise ValueError('unknown allowed tool')
                from pathlib import Path
                bound = policy.get('project')
                working_directory = Path(bound).expanduser().resolve() if bound else None
                if working_directory and (working_directory.is_file() or working_directory.suffix == '.toml'):
                    working_directory = working_directory.parent
                registry = ClientRegistry([remote_tool(t) for t in selected], jobs=JobManager(budget=policy.get('budget'), working_directory=working_directory), project=str(Path(bound).expanduser().resolve()) if bound else None, profile=profile, workflow=workflow, output=policy.get('output'))
            self.clients[token] = (registry, build_server(registry), SseServerTransport('/messages'))

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    for registry, _, _ in self.clients.values():
                        registry.jobs.shutdown()
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        if scope['type'] != 'http':
            return
        headers = dict(scope['headers'])
        auth = headers.get(b'authorization', b'').decode('latin1')
        token = auth.removeprefix('Bearer ') if auth.startswith('Bearer ') else ''
        client = next((c for key, c in self.clients.items() if hmac.compare_digest(key, token)), None)
        from starlette.responses import JSONResponse
        if client is None:
            return await JSONResponse({'error': 'authentication required'}, 401)(scope, receive, send)
        registry, server, transport = client
        if scope['path'] == '/sse' and scope['method'] == 'GET':
            async with transport.connect_sse(scope, receive, send) as streams:
                from mcp.server.lowlevel import NotificationOptions
                await server.run(*streams, server.create_initialization_options(NotificationOptions(tools_changed=True)))
        elif scope['path'] == '/messages':
            await transport.handle_post_message(scope, receive, send)
        else:
            await JSONResponse({'error': 'unknown endpoint'}, 404)(scope, receive, send)


def serve(clients, host='127.0.0.1', port=8766, *, profile='all', workflow=None):
    import uvicorn
    uvicorn.run(Remote(clients, profile=profile, workflow=workflow), host=host, port=port)
