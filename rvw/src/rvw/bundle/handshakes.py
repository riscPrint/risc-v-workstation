"""Valid/ready channel activity over a wave window: how often each channel fired, when it last
fired, and which requests (by id) got no response. Core config:

    [handshakes]
    scope = '^TOP\\.BoomSimTop\\.'
    clock = 'clk'                                    # relative to scope
    requests = ["a"]                                 # channels that open a transaction by id
    responses = ["d"]                                # channels that close one
    [handshakes.channels]
    a = { valid = 'io_mem_a_valid', ready = 'io_mem_a_ready', id = 'io_mem_a_payload_source', info = 'io_mem_a_payload_address' }
    d = { valid = 'io_mem_d_valid', ready = 'io_mem_d_ready', id = 'io_mem_d_payload_source' }

Optional opcode matching, so that a response of one transaction type cannot close a request of
another type that happens to use the same id (TileLink: a D ReleaseAck for a C Release must not
close an A Get with the same source):

    [handshakes.channels]
    a = { ..., opcode = 'io_mem_a_payload_opcode' }
    [handshakes.opens]          # request channel -> opcodes that expect a response (default: all)
    c = [6, 7]                  # Release, ReleaseData (ProbeAck gets no response)
    [handshakes.closes]         # response channel -> request channel -> response opcodes answering it
    d = { a = [0, 1, 2, 4, 5], c = [6] }

Without [handshakes.closes] for a response channel, a response closes the open request with its id
on any request channel.

A channel fires on a rising clock edge when valid and ready were both 1 just before the edge.
Requests opened before the window started are not seen, so "open" lists only requests issued
inside the window.
"""
from __future__ import annotations

import re

from ..wave import vcd


def analyze(cfg: dict, wave: str, t_end: int | None = None, period: int = 1) -> dict:
    scope = re.compile(cfg.get("scope", ""))
    chans = cfg.get("channels") or {}
    with vcd.open_text(wave) as f:
        hdr = vcd.read_header(f)
        rel = {}
        for v in hdr.vars:
            m = scope.search(v.name)
            if m:
                rel.setdefault(v.name[m.end():], v)

        def code(pat):
            if not pat:
                return None
            rx = re.compile(pat)
            for name, v in rel.items():
                if rx.fullmatch(name):
                    return v.code
            return None

        clk = code(cfg.get("clock", "clk"))
        spec = {}
        for n, c in chans.items():
            spec[n] = {k: code(c.get(k)) for k in ("valid", "ready", "id", "info", "opcode")}
        missing = [n for n, s in spec.items() if not s["valid"] or not s["ready"]]
        if clk is None or len(missing) == len(spec):
            return {"error": "clock or channels not found in the wave", "missing": missing}
        want = {clk} | {c for s in spec.values() for c in s.values() if c}
        vals: dict[str, str] = {}
        stats = {n: {"fires": 0, "last_fire": None, "valid_now": None, "ready_now": None,
                     "stalled_since": None, "unknown_opcode_fires": 0,
                     "last_unknown_opcode": None} for n in spec if n not in missing}
        open_req: dict[tuple[str, int], dict] = {}
        reqs, resps = set(cfg.get("requests", [])), set(cfg.get("responses", []))
        opens = {k: {int(x) for x in v} for k, v in (cfg.get("opens") or {}).items()}
        closes = {k: {rc: {int(x) for x in ops} for rc, ops in v.items()}
                  for k, v in (cfg.get("closes") or {}).items()}
        batch: list[tuple[str, str]] = []
        now = None
        first = None

        def flush(t):
            # rising clock edge in this batch? sample before applying it
            rising = (any(c == clk and vcd.to_int(v) == 1 for c, v in batch)
                      and vcd.to_int(vals.get(clk)) == 0)
            if rising:
                fires = []
                for n, s in spec.items():
                    if n in missing:
                        continue
                    st = stats[n]
                    valid = vcd.to_int(vals.get(s["valid"]))
                    ready = vcd.to_int(vals.get(s["ready"]))
                    if valid == 1 and ready == 1:
                        st["fires"] += 1
                        st["last_fire"] = t
                        ident = vcd.to_int(vals.get(s["id"])) if s["id"] else None
                        op = vcd.to_int(vals.get(s["opcode"])) if s["opcode"] else None
                        opcode_expected = bool(chans[n].get("opcode")) or n in opens or n in closes
                        if opcode_expected and op is None:
                            st["unknown_opcode_fires"] += 1
                            st["last_unknown_opcode"] = {"time": t, "value": vals.get(s["opcode"])}
                        fires.append((n, s, ident, op, opcode_expected))
                    if valid == 1 and ready == 0:
                        if st["stalled_since"] is None:
                            st["stalled_since"] = t
                    else:
                        st["stalled_since"] = None
                # First close only transactions that existed before this edge. A same-edge
                # response cannot prove that a new request completed (zero latency is ambiguous).
                for n, s, ident, op, opcode_expected in fires:
                    if n not in resps or ident is None:
                        continue
                    rule = closes.get(n)
                    # Unknown opcodes prove no match when an opcode or rule is configured.
                    if op is not None or not opcode_expected:
                        for rc in sorted(reqs):
                            if rule is None or (rc in rule and op in rule[rc]):
                                open_req.pop((rc, ident), None)
                # Then open new requests, including replacements with the same id.
                for n, s, ident, op, _ in fires:
                    if n in reqs and ident is not None:
                        if n not in opens or (op is not None and op in opens[n]):
                            open_req[(n, ident)] = {
                                "channel": n, "id": hex(ident), "opcode": op, "time": t,
                                "info": vcd.fmt_value(vals[s["info"]]) if s["info"] in vals else None}
            for c, v in batch:
                vals[c] = v
            batch.clear()

        for t, cd, raw in vcd.body_records(f):
            if now is not None and t != now:
                flush(now)
            if t_end is not None and t > t_end:
                now = None
                break
            now = t
            if first is None:
                first = t
            if cd in want:
                batch.append((cd, raw))
        if now is not None:
            flush(now)
        end = now if t_end is None else t_end
        for n, s in spec.items():
            if n in missing:
                continue
            st = stats[n]
            st["valid_now"] = vals.get(s["valid"])
            st["ready_now"] = vals.get(s["ready"])
    per = max(period, 1)
    out = {"window": [first, end], "channels": {}, "open_requests": [], "missing": missing}
    for n, st in stats.items():
        d = {"fires": st["fires"], "valid": st["valid_now"], "ready": st["ready_now"]}
        if st["last_fire"] is not None and end is not None:
            d["cycles_since_last_fire"] = (end - st["last_fire"]) // per
        if st["stalled_since"] is not None and end is not None:
            d["stalled_cycles"] = (end - st["stalled_since"]) // per
        if st["unknown_opcode_fires"]:
            d["unknown_opcode_fires"] = st["unknown_opcode_fires"]
            d["last_unknown_opcode"] = st["last_unknown_opcode"]
        out["channels"][n] = d
    for _, r in sorted(open_req.items()):
        r = dict(r)
        if end is not None:
            r["age_cycles"] = (end - r.pop("time")) // per
        out["open_requests"].append(r)
    return out


def render_md(h: dict) -> str:
    if "error" in h:
        return f"- handshakes: {h['error']}"
    lines = []
    for n, d in h["channels"].items():
        s = f"- `{n}`: {d['fires']} fires in window"
        if "cycles_since_last_fire" in d:
            s += f", last {d['cycles_since_last_fire']} cycles before the end"
        else:
            s += ", none in window"
        s += f"; now valid={d['valid']} ready={d['ready']}"
        if "stalled_cycles" in d:
            s += f" (**valid without ready for {d['stalled_cycles']} cycles**)"
        if d.get("unknown_opcode_fires"):
            last = d["last_unknown_opcode"]
            s += (f"; **unknown opcode on {d['unknown_opcode_fires']} fires**"
                  f" (last value={last['value']} at time {last['time']})")
        lines.append(s)
    if h["open_requests"]:
        lines.append("- requests without a response (issued in the window): " + ", ".join(
            f"{r['channel']} id={r['id']}" + (f" opcode={r['opcode']}" if r.get("opcode") is not None else "")
            + (f" addr={r['info']}" if r.get("info") else "") +
            f" ({r.get('age_cycles')} cycles old)" for r in h["open_requests"]))
    return "\n".join(lines)
