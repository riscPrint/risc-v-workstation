"""Which consumer tools each probe kind enables. Generic: no core names.

Each consumer lists `needs`: (kind, required fields) pairs that must all be present,
the existing format the converter writes, and the `rvw probes convert --to` name.
`converter=None` means no writer exists yet; such a consumer is reported as a gap.
"""
from __future__ import annotations

CONSUMERS = [
    dict(id="perf-causal", tool="rvw perf (measured causes and dependencies)",
         needs=[("stage", ["id"]), ("retire", ["id"]), ("stall", []), ("dependency", ["id", "producer"])],
         format="Kanata 0004 with stall and W records", converter="kanata",
         note="measured reason samples identify blocked cycles; dependency edges alone are not causes"),
    dict(id="csim-compare-rtl", tool="rvw csim compare-rtl", needs=[("branch", ["pc", "taken", "target", "predicted_taken"])],
         format="rvw.bp-events/1", converter="bp-events",
         note="branch events at the commit point, aligned to C2 retirements"),
    dict(id="perf-pipeline", tool="rvw perf", needs=[("stage", ["id"]), ("retire", ["id"])],
         format="Kanata 0004", converter="kanata", note="stage occupancy, retire and flush per instruction ID"),
    dict(id="perf-predictions", tool="rvw perf (prediction outcomes)",
         needs=[("stage", ["id"]), ("retire", ["id"]), ("branch", ["id", "taken", "predicted_taken"])],
         format="Kanata 0004 #rvw prediction records", converter="kanata",
         note="branch events carry the stage probes' instruction ID; direction outcomes only"),
    dict(id="perf-stalls", tool="rvw perf (stall causes)", needs=[("stage", ["id"]), ("retire", ["id"]), ("stall", [])],
         format="Kanata 0004 #rvw stall records", converter="kanata", note="one measured sample per blocked cycle"),
    dict(id="cache-observer", tool="RiscvSim CacheEventObserver", needs=[("cache", ["address", "data"])],
         format="cache observer event JSONL", converter="cache", note="bytes are needed for the content scoreboard"),
    dict(id="cache-check", tool="rvw probes convert --to cache-check (scoreboard and memory image)",
         needs=[("cache", ["address", "data"])], format="rvw.probe-cache-check/1", converter="cache-check",
         note="fill/writeback bytes against the ELF plus retired C2 stores; hits need a resident line"),
    dict(id="csim-compare-cache", tool="rvw csim compare-cache", needs=[("cache", ["address", "hit"])],
         format="rvw.probe-events/1 cache access events", converter="(reads the stream)",
         note="reads the event stream directly: access events with hit at the commit point, one per retired access"),
    dict(id="mmu-protocol", tool="rvw regress mmu report --protocol-config", needs=[("tlb", ["va", "pa"])],
         format="rvw.mmu-observations/1", converter="mmu", note="tlb_fill, tlb_hit and tlb_invalidate rows"),
    dict(id="mmu-walk-records", tool="rvw regress mmu report (C2 mmu_walks)",
         needs=[("walk", ["level", "address"]), ("walk", ["va", "access", "root", "status", "pa"])],
         format="C2 mmu_walks records", converter="mmu-walks",
         note="response events grouped per walk up to Probe.walkResult, attached to retirements"),
    dict(id="mmu-walk-capture", tool="rvw regress mmu report (observations)", needs=[("walk", ["address"])],
         format="rvw.mmu-observations/1", converter="mmu", note="walk_request and walk_response rows"),
    dict(id="ooo-calibration", tool="rvw arch ooo-calibrate", needs=[("counter", ["inc"])],
         format="RTL event counts (c1_sha256, trace_sha256, counts)", converter="counts",
         note="name counters as the plan's rtl_event names"),
    dict(id="hpm-bindings", tool="SpinalChecks HpmControlChecks and HPM monitors", needs=[("counter", ["inc"], "hpm")],
         format="rvw.hpm-bindings/1", converter="hpm", note="counter probes with an hpm selector value"),
    dict(id="etrace", tool="rvw debug etrace", needs=[("trace", ["itype", "iaddr", "iretire", "ilastsize", "priv"])],
         format="E-Trace encoder ingress CSV", converter="etrace-ingress", note="DUT encoder ingress, not C2-derived"),
    dict(id="cosim-interrupts", tool="rvw cosim (interrupt-taken evidence)", needs=[("interrupt", ["cause", "pc"])],
         format="rvw.probe-interrupts/1 check against C2 trap events", converter="interrupts",
         note="independent check of C2 interrupt traps"),
    dict(id="bus-check", tool="rvw probes convert --to bus (C2 memory access check)",
         needs=[("bus", ["address", "write"])], format="rvw.probe-bus-check/1", converter="bus",
         note="data bus requests before any cache, against retired C2 loads and stores"),
    dict(id="csr-write-check", tool="rvw probes convert --to csr-writes (C2 CSR instruction check)",
         needs=[("csr", ["address", "value"])], format="rvw.probe-csr-writes/1", converter="csr-writes",
         note="CSR write port events against retired C2 CSR instructions and their operands"),
    dict(id="cosim-csr-slots", tool="rvw cosim (per-slot CSR state)", needs=[("csr", ["address", "value"])],
         format="C2/2 csr_snapshot", converter=None,
         note="needs per-slot CSR state through RvfiProbe csrSlots; write events alone cannot fill a snapshot"),
    dict(id="fault-sites", tool="rvw fault plan --sites", needs=[("fault", ["value"])],
         format="rvw fault site list", converter="fault-sites",
         note="register paths from Probe.faultSite; the adapter must implement C1 --fault"),
]


def _have(probes, kind, fields, meta=None):
    """Probes of `kind` with all `fields` (and the meta key, when the meta is known)."""
    out = []
    for p in probes:
        if p["kind"] != kind or not set(fields) <= set(p["fields"]):
            continue
        if meta and p.get("meta") is not None and meta not in p["meta"]:
            continue
        out.append(p)
    return out


def matrix(probes: list[dict]) -> list[dict]:
    """One row per consumer: status `enabled`, `missing` or `no_converter`.

    `probes` are dicts with `kind`, `name`, `fields` (names) and `meta` (None when unknown,
    as in a design database)."""
    rows = []
    for c in CONSUMERS:
        missing, used = [], []
        for need in c["needs"]:
            kind, fields = need[0], need[1]
            meta = need[2] if len(need) > 2 else None
            found = _have(probes, kind, fields, meta)
            if found:
                used += [f"{p['kind']}/{p['name']}" for p in found]
            else:
                missing.append(f"{kind}({', '.join(fields)}{', meta ' + meta if meta else ''})")
        status = "missing" if missing else ("enabled" if c["converter"] else "no_converter")
        unknown = [f"{p['kind']}/{p['name']}" for need in c["needs"] if len(need) > 2
                   for p in _have(probes, need[0], need[1]) if p.get("meta") is None]
        row = dict(consumer=c["id"], tool=c["tool"], status=status, format=c["format"], converter=c["converter"],
                   probes=sorted(set(used)), missing=missing, note=c["note"])
        if unknown and status == "enabled":
            row["status"] = "unknown"
            row["missing"] = ["probe meta is not in the design database; check an event stream"]
        rows.append(row)
    return rows
