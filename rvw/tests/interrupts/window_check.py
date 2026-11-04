"""Independent bounds for adapter interrupt regressions, separate from Spike injection.

The caller supplies windows before execution. Never derive them from DUT traps.
This check does not replace the instruction comparison with Spike.
"""
from rvw.cosim.trace import Trace


def check_interrupts(path, schedule, *, cause=None, window=None, handler_pc=None,
                     mode=None, epc_range=None):
    trace = Trace(path)
    try:
        rows = list(trace)
    finally:
        trace.close()
    if not schedule or not any(r.get("event") == "end" for r in rows):
        return {"status": "inconclusive", "reason": "missing schedule or end evidence"}
    end = rows[-1]["cycle"]
    expected = []
    for cycle, level in schedule:
        if cycle <= end and (not expected or level != expected[-1][1]):
            expected.append((cycle, level))
    driven = [(r["cycle"], r["levels"]) for r in rows if r.get("event") == "irq"]
    if driven != expected:
        return {"status": "mismatch", "reason": "driven inputs differ from schedule"}
    instructions = [r for r in rows if "order" in r]
    if not instructions:
        return {"status": "inconclusive", "reason": "no instruction evidence"}
    traps = [r for r in rows if r.get("event") == "trap"]
    if cause is None:
        return {"status": "mismatch" if traps else "consistent", "reason": "masked interval"}
    if window is None or handler_pc is None or mode is None or epc_range is None:
        return {"status": "inconclusive", "reason": "missing independent interrupt bounds"}
    if not traps:
        return {"status": "inconclusive", "reason": "no interrupt observed"}
    if len(traps) != 1 or not traps[0]["intr"] or traps[0]["cause"] != cause:
        return {"status": "mismatch", "reason": "unexpected trap cause or count"}
    trap = traps[0]
    if not window[0] <= trap["cycle"] <= window[1]:
        return {"status": "mismatch", "reason": "interrupt outside independent window"}
    handler = next((i for i, r in enumerate(instructions) if r["pc"] == handler_pc), None)
    if handler is None or handler == 0 or handler + 2 >= len(instructions):
        return {"status": "inconclusive", "reason": "missing trap-entry instructions"}
    entry = instructions[handler:handler + 3]
    # Programs read xcause, xepc, xstatus into s1, s2, s3 in that order.
    if ([r["rd"] for r in entry] != [9, 18, 19] or entry[0]["rd_wdata"] != cause
            or any(r["mode"] != mode for r in entry)
            or not epc_range[0] <= entry[1]["rd_wdata"] < epc_range[1]
            or entry[2]["rd_wdata"] & (8 if mode == 3 else 2)):
        return {"status": "mismatch", "reason": "trap-entry state differs from program contract"}
    before = instructions[handler - 1]
    if before["pc"] not in range(*epc_range) and before["pc_next"] != epc_range[0]:
        return {"status": "mismatch", "reason": "interrupt interrupted the masked instruction region"}
    if rows[-1].get("status") != "pass":
        return {"status": "inconclusive", "reason": "program did not pass"}
    return {"status": "consistent", "reason": "schedule, independent window and entry state checked"}
