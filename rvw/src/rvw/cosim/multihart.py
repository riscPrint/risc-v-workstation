"""Serialized retirement comparison with independent per-hart checker state."""
from concurrent.futures import ThreadPoolExecutor
import json
import socket
from .checker import c2_view
from .lockstep import serve_connection
from .spike import _SPIKE_LOCK


class HartModel:
    def __init__(self, model, hart):
        self.model, self.hart = model, hart
        self.regs = [0]*32

    def __getattr__(self, key):
        member = getattr(self.model, key)
        if not callable(member):
            return member
        def invoke(*args, **kwargs):
            with _SPIKE_LOCK:
                self.model.select_hart(self.hart)
                self.model.regs = self.regs
                try:
                    return member(*args, **kwargs)
                finally:
                    self.regs = list(self.model.regs)
        return invoke


def check_multihart(trace, model, platform, *, history, sync):
    """One shared reference RAM. Capture order is the required visibility order.

    This is a sequentially consistent serialized-retirement profile. It cannot
    adjudicate weak-memory outcomes or external-agent writes.
    """
    if trace.header.get('memory_profile') != 'serialized-retirement':
        trace.close()
        raise ValueError('multi-hart cosim requires memory_profile=serialized-retirement')
    if not hasattr(model, 'add_hart'):
        trace.close()
        raise ValueError('reference cannot compare multiple harts')
    header = dict(trace.header)
    harts = header.pop('harts')
    caps = [c for c in header.get('capabilities', ['multihart']) if c != 'multihart']
    if caps:
        header['capabilities'] = caps
    else:
        header.pop('capabilities', None)
        header['schema'] = 'rvw.rvfi/1'
    clients, peers, futures, reports, reset = {}, {}, {}, {}, set()
    pool = ThreadPoolExecutor(max_workers=len(harts))
    def send(hart, record):
        stream = clients[hart]
        stream.write((json.dumps(record)+'\n').encode())
        stream.flush()
        response = stream.readline()
        if not response:
            raise ValueError('per-hart checker disconnected')
        return json.loads(response)
    try:
        for hart in harts:
            model.add_hart(hart)
            server, client = socket.socketpair()
            server.settimeout(30)
            client.settimeout(30)
            peers[hart] = (server, client)
            clients[hart] = client.makefile('rwb')
            futures[hart] = pool.submit(serve_connection, server, HartModel(model, hart), platform,
                                        reproduction={}, history=history, sync=sync)
            response = send(hart, header)
            if response['status'] != 'continue':
                raise ValueError(response.get('error', 'invalid per-hart header'))
        for record in trace:
            event = record.get('event')
            if event == 'external':
                raise ValueError('serialized cosim does not support external-agent events')
            hart = record['hart']
            if event == 'reset':
                if record['epoch'] != 0 or hart in reset:
                    raise ValueError('reference supports initial reset only')
                reset.add(hart)
                continue
            row = c2_view({k: v for k, v in record.items() if k not in ('hart', 'epoch', 'capture_seq')})
            if event == 'irq':
                row['levels'] = hex(row['levels'])
            if event == 'hart_end':
                row['event'] = 'end'
            response = send(hart, row)
            if response['status'] != 'continue':
                reports[str(hart)] = response
                if response['status'] != 'match':
                    return dict(schema='rvw.cosim/1', status=response['status'], hart=hart,
                                harts=reports, mismatch=response.get('mismatch'),
                                memory_profile='serialized-retirement')
        complete = len(reports) == len(harts)
        return dict(schema='rvw.cosim/1', status='match' if complete else 'inconclusive',
                    trace_complete=complete, harts=reports,
                    instructions=sum(r.get('instructions', 0) for r in reports.values()),
                    memory_profile='serialized-retirement',
                    scope='capture order; shared RAM; no weak-memory or external-agent claim')
    finally:
        trace.close()
        for server, client in peers.values():
            for endpoint in (server, client):
                try:
                    endpoint.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        for stream in clients.values():
            stream.close()
        for server, client in peers.values():
            server.close()
            client.close()
        pool.shutdown(wait=True)
