from rvw.farm.mcp_tools import mcp_tools
from rvw.evidence.mcp_tools import mcp_tools as evidence_tools
from rvw.mcp.registry import Registry


def test_long_farm_tools_use_owned_workers(tmp_path):
    tools = mcp_tools() + evidence_tools()
    assert all(t.wants_job for t in tools if t.long)
    registry = Registry(tools)
    try:
        record = registry.call('farm_queue', dict(root=str(tmp_path), operation='list'))
        job = registry.jobs.get(record['job_id'])
        assert job.done.wait(10)
        assert job.status == 'done'
        assert job.result == []
    finally:
        registry.jobs.shutdown()
