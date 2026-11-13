"""Blocking C2 transport. Acknowledgement follows architectural comparison."""
import json
from .checker import check, SYNC_KINDS


def serve_connection(connection, model, platform, *, reproduction, history=10, sync=SYNC_KINDS):
    """Serve one connected socket. Events must precede affected retirements.

    Send a C2 header, then one C2 record per request. Wait for each reply.
    `continue` permits the next record; any other status stops the simulator.
    The end request receives the final C5-compatible report.
    """
    stream = connection.makefile("rwb")

    def reply(value):
        stream.write((json.dumps(value) + "\n").encode())
        stream.flush()

    class Lines:
        pending = False
        ended = False

        def __iter__(self):
            return self

        def __next__(self):
            if self.ended:
                raise StopIteration
            if self.pending:
                reply({"status": "continue"})
            line = stream.readline()
            if not line:
                raise ValueError("lockstep peer disconnected before end")
            obj = json.loads(line)
            self.ended = obj.get("event") == "end"
            self.pending = True
            return line.decode()

        def readline(self):
            return next(self, "")

        def close(self):
            pass

    try:
        result = check(Lines(), model, platform, history=history, sync=sync, ordered_events=True)
        result.update(mode="lockstep", reproduction=reproduction,
                      event_order="before affected retirement")
        if result['status'] == 'match' and not result['trace_complete']:
            result.update(status='inconclusive', cause='lockstep_incomplete')
    except (ValueError, KeyError, TypeError) as exc:
        result = dict(schema="rvw.cosim/1", status="error", mode="lockstep", error=str(exc),
                      reproduction=reproduction)
    try:
        reply(result)
    finally:
        stream.close()
    return result
