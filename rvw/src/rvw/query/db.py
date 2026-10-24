"""Read access to a SpinalDB design database (`rvw.designdb/20`, see SpinalDB/README.md).

Name resolution accepts every name a user or an agent is likely to hold:

- RTL/Verilog paths: `core.rob.rob_head` (instance path + Verilog name), optionally with the
  toplevel module first (`BoomSimTop.tile.core...`), or `Module.name` for a module instantiated once;
- waveform paths: `TOP.BoomSimTop.tile.core.rob.rob_head`, `/` separators, `[i]` indexes and
  `[hi:lo]` ranges as Surfer shows them;
- Spinal paths: `core.rob.io.enq.valids(0)` / `core.rob.io.enq.valids.0`, Area-scoped names
  (`fetch.logic.ptr.push`), and mixes such as `core.rob.io.enq_valids_0`;
- a unique suffix (`rob_head`, `rob.io.enq.valids.0`).

A name that matches a bundle or Area prefix instead of one signal resolves to the group of its
signals (an "interface"), used by `fanin`/`fanout`/`path`.
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rvw.common.proc import run_group
from rvw.common.capture import Capture, CaptureError

SCHEMA = "rvw.designdb/20"
# Navigation reads older schemas; diff requires the current typed-key contract.
READABLE = {"rvw.designdb/1", "rvw.designdb/2", "rvw.designdb/3", "rvw.designdb/4", "rvw.designdb/5",
            "rvw.designdb/6", "rvw.designdb/7", "rvw.designdb/8", "rvw.designdb/9", "rvw.designdb/10", "rvw.designdb/11",
            "rvw.designdb/12", "rvw.designdb/13", "rvw.designdb/14", "rvw.designdb/15", "rvw.designdb/16", "rvw.designdb/17", "rvw.designdb/18", "rvw.designdb/19", SCHEMA}
# Schemas whose clock domains record the clock-enable and soft-reset polarity (/4 on).
_POLARITY = {"rvw.designdb/4", "rvw.designdb/5", "rvw.designdb/6", "rvw.designdb/7", "rvw.designdb/8", "rvw.designdb/9",
             "rvw.designdb/10", "rvw.designdb/11", "rvw.designdb/12", "rvw.designdb/13", "rvw.designdb/14", "rvw.designdb/15", "rvw.designdb/16", "rvw.designdb/17", "rvw.designdb/18", "rvw.designdb/19", SCHEMA}


CAPTURE_SCHEMAS = {"rvw.designdb/18", "rvw.designdb/19", SCHEMA}
STATE_SCHEMAS = {"rvw.designdb/17", *CAPTURE_SCHEMAS}


class QueryError(Exception):
    """A query that cannot be answered as asked (unknown name, ambiguous name, bad database)."""

    def __init__(self, message: str, candidates: list[str] | None = None):
        super().__init__(message)
        self.candidates = candidates or []

    def to_json(self) -> dict:
        d = {"error": str(self)}
        if self.candidates:
            d["candidates"] = self.candidates
        if str(self).startswith("input_not_captured:"):
            d["status"] = "inconclusive"
            d["cause"] = ":".join(str(self).split(":", 2)[:2])
        return d


def default_db() -> str | None:
    """`$RVW_DESIGNDB`, else `design.db` in the current directory when it exists."""
    from rvw.common.project import database
    selected, _ = database()
    if selected is not None:
        return str(selected)
    env = os.environ.get("RVW_DESIGNDB")
    if env:
        return env
    return "design.db" if Path("design.db").exists() else None


def run_on(path, fn):
    """Run one query on its captured database, then release the private copy."""
    db = DesignDB(Path(path).expanduser() if path is not None else None)
    try:
        result = fn(db)
        if isinstance(result, dict):
            result["input_capture"] = db.capture.record()
            stale = db.staleness()
            if stale:
                result["db_warnings"] = stale
        return result
    finally:
        db.close()


@dataclass
class Signal:
    id: int
    path: str
    spinal_path: str
    name: str
    kind: str
    direction: str | None
    type: str
    width: int
    data_type: str | None
    component_id: int
    area_id: int | None
    clock_domain_id: int | None
    reset_value: str | None
    clock_role: str | None
    generated: bool
    pruned: bool
    file: str | None
    line: int | None

    @property
    def is_reg(self) -> bool:
        return self.kind == "reg"


_SIG_COLS = ("s.id, s.path, s.spinal_path, s.name, s.kind, s.direction, s.type, s.width, s.data_type, s.component_id, "
             "s.area_id, s.clock_domain_id, s.reset_value, s.clock_role, s.generated, s.pruned, f.path, s.line")


def _sig(row) -> Signal:
    return Signal(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11],
                  row[12], row[13], bool(row[14]), bool(row[15]), row[16], row[17])


class DesignDB:
    def __init__(self, path: str | os.PathLike | None, *, capture: Capture | None = None):
        if path is None:
            raise QueryError("no design database: pass --db PATH or set RVW_DESIGNDB")
        p = Path(path)
        if not p.exists():
            raise QueryError(f"design database not found: {p}")
        self._private = tempfile.TemporaryDirectory(prefix="rvw-query-") if capture is None else None
        try:
            self.capture = capture if capture is not None else Capture(Path(self._private.name) / "inputs")
            self.input = self.capture.file(p)
            self.path = Path(self.input.source)
            # Published SpinalDB files use rollback journals and atomic rename. A WAL database
            # cannot be captured as one input file. Do not silently omit its committed pages.
            with self.input.copy.open("rb") as stream:
                header = stream.read(20)
            if header[18:20] != b"\x01\x01":
                raise QueryError("input_not_captured:database: WAL or invalid SQLite header")
            self.conn = sqlite3.connect(self.input.copy.as_uri() + "?mode=ro&immutable=1", uri=True,
                                        check_same_thread=False)
            self.meta = dict(self.conn.execute("SELECT key, value FROM meta"))
        except (CaptureError, sqlite3.DatabaseError, QueryError) as e:
            if hasattr(self, "conn"):
                self.conn.close()
            if self._private is not None:
                self._private.cleanup()
            raise QueryError(f"input_not_captured:database: {e}") from e
        if self.meta.get("schema") not in READABLE:
            self.close()
            raise QueryError(f"{p}: schema {self.meta.get('schema')!r}, expected {SCHEMA!r}")
        self.schema = self.meta["schema"]
        self.top = self.meta.get("toplevel", "")
        self._inout_edges_checked = False
        self.signal_by_id = lru_cache(maxsize=200_000)(self._signal_by_id)
        self.component = lru_cache(maxsize=20_000)(self._component)
        self.cond_chain = lru_cache(maxsize=100_000)(self._cond_chain)
        self.clock_domain = lru_cache(maxsize=1000)(self._clock_domain)
        self.area = lru_cache(maxsize=20_000)(self._area)

    def close(self):
        self.conn.close()
        if self._private is not None:
            self._private.cleanup()

    def capture_record(self) -> dict:
        """This database's input record, even when a diff shares one Capture for both sides."""
        record = self.capture.record()
        record["files"] = [item for item in record["files"] if item["source"] == self.input.source]
        return record

    def require_inout_edges(self) -> None:
        """Refuse old incomplete graphs without changing the table or typed-key contract."""
        if self._inout_edges_checked:
            return
        if not self.q("SELECT 1 FROM signals WHERE direction = 'inout' LIMIT 1"):
            self._inout_edges_checked = True
            return
        missing = self.q("""
            SELECT 1 FROM signals i JOIN signals o ON i.component_id = o.component_id
            JOIN components c ON c.id = i.component_id
            WHERE c.blackbox = 1 AND i.id != o.id
              AND i.direction IN ('in', 'inout') AND o.direction IN ('out', 'inout')
              AND (i.direction = 'inout' OR o.direction = 'inout')
              AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.src = i.id AND e.dst = o.id AND e.kind = 'blackbox')
            LIMIT 1
        """)
        if not missing:
            missing = self.q("""
                SELECT 1 FROM assignments a JOIN assign_reads r ON r.assignment_id = a.id
                JOIN signals t ON t.id = a.target_id JOIN signals s ON s.id = r.signal_id
                WHERE t.direction = 'inout' AND s.direction = 'inout' AND r.kind = 'data'
                  AND a.kind = 'data'
                  AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.src = t.id AND e.dst = s.id AND e.kind = 'data')
                LIMIT 1
            """)
        if missing:
            raise QueryError("incomplete inout dependency graph. Rebuild the database with the current SpinalDB.")
        self._inout_edges_checked = True

    def staleness(self) -> list[str]:
        """Warnings when the sources the database was built from differ from the checkout now.

        Uses the `core_repo`/`core_rev`/`core_dirty` meta rows (BOOM entry), or the generic
        `source_repo`/`source_rev`/`source_dirty` (`--meta`). Nothing is said when they are absent."""
        m = self.meta
        repo = m.get("core_repo") or m.get("source_repo")
        rev = m.get("core_rev") or m.get("source_rev")
        dirty = m.get("core_dirty") or m.get("source_dirty")
        if not repo or not rev:
            return []
        if not Path(repo).is_dir():
            return [f"cannot check that the database is current: source checkout {repo} not found"]
        head = run_group(["git", "-C", repo, "rev-parse", "HEAD"], capture=True, timeout=30)
        status = run_group(["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"], capture=True,
                           timeout=60)
        if head.returncode or status.returncode:
            return [f"cannot check that the database is current: git failed in {repo}"]
        out = []
        now = head.stdout.strip()
        if not now.startswith(rev):
            out.append(f"database is older than the sources: built from {rev}, {repo} is now at {now[:12]}; "
                       f"rebuild it")
        if status.stdout.strip():
            out.append(f"{repo} has uncommitted changes; the database may not match them")
        if dirty == "true":
            out.append(f"database was built from a checkout with uncommitted changes at {rev}; "
                       f"it cannot be matched to a revision")
        return out

    def q(self, sql: str, args=()) -> list:
        return self.conn.execute(sql, args).fetchall()

    # ------------------------------------------------------------------ rows
    def _signal_by_id(self, sid: int) -> Signal:
        row = self.conn.execute(f"SELECT {_SIG_COLS} FROM signals s LEFT JOIN files f ON f.id = s.file_id WHERE s.id = ?",
                                (sid,)).fetchone()
        if row is None:
            raise QueryError(f"no signal with id {sid}")
        return _sig(row)

    def signals_where(self, where: str, args=(), limit: int | None = None) -> list[Signal]:
        sql = f"SELECT {_SIG_COLS} FROM signals s LEFT JOIN files f ON f.id = s.file_id WHERE {where}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [_sig(r) for r in self.q(sql, args)]

    def _component(self, cid: int) -> dict:
        r = self.conn.execute("SELECT c.id, c.parent_id, c.path, c.name, c.module, c.class_name, c.blackbox, c.depth, f.path, c.line "
                              "FROM components c LEFT JOIN files f ON f.id = c.file_id WHERE c.id = ?", (cid,)).fetchone()
        if r is None:
            raise QueryError(f"no component with id {cid}")
        return {"id": r[0], "parent_id": r[1], "path": r[2], "name": r[3], "module": r[4], "class": r[5],
                "blackbox": bool(r[6]), "depth": r[7], "loc": loc(r[8], r[9])}

    def _clock_domain(self, cid: int | None) -> dict | None:
        if cid is None:
            return None
        polarity = ("clock_enable_active_high, soft_reset_active_high" if self.schema in _POLARITY else "NULL, NULL")
        r = self.conn.execute("SELECT clock, reset, reset_kind, reset_active_high, clock_enable, soft_reset, clock_edge, "
                              f"{polarity} FROM clock_domains WHERE id = ?", (cid,)).fetchone()
        if r is None:
            return None
        d = {"clock": r[0], "edge": r[6]}
        if r[1]:
            d["reset"] = r[1]
            d["reset_kind"] = r[2]
            d["reset_active"] = "high" if r[3] == "true" else "low"
        if r[4]:
            d["clock_enable"] = r[4]
            if r[7] is not None:
                d["clock_enable_active"] = "high" if r[7] == "true" else "low"
        if r[5]:
            d["soft_reset"] = r[5]
            if r[8] is not None:
                d["soft_reset_active"] = "high" if r[8] == "true" else "low"
        return d

    def _area(self, aid: int | None) -> str | None:
        if aid is None:
            return None
        r = self.conn.execute("SELECT path FROM areas WHERE id = ?", (aid,)).fetchone()
        return r[0] if r else None

    def _cond_chain(self, cid: int | None) -> tuple:
        """Enclosing conditions of a statement, outermost first."""
        out = []
        while cid is not None:
            r = self.conn.execute("SELECT c.parent_id, c.kind, c.expr, c.keys, f.path, c.line FROM conds c "
                                  "LEFT JOIN files f ON f.id = c.file_id WHERE c.id = ?", (cid,)).fetchone()
            if r is None:
                break
            out.append({"kind": r[1], "expr": r[2], "keys": r[3], "loc": loc(r[4], r[5])})
            cid = r[0]
        return tuple(reversed(out))

    def wave_path(self, path: str) -> str:
        scopes = self.meta.get("extra_scopes", f"TOP {self.top}").split()
        return ".".join(scopes + ([path] if path else []))

    def signal_json(self, s: Signal, brief: bool = False) -> dict:
        d = {"path": s.path, "kind": s.kind}
        if s.direction:
            d["direction"] = s.direction
        d["type"] = s.type
        d["width"] = s.width
        if brief:
            if s.generated:
                d["generated"] = True
            d["loc"] = loc(s.file, s.line)
            return d
        comp = self.component(s.component_id)
        d["spinal_path"] = s.spinal_path
        if s.data_type:
            d["data_type"] = s.data_type
        d["component"] = comp["path"] or self.top
        if s.kind == "mem_read":
            d["origin"] = "synchronous memory read port state (database node)"
            d["clock_domain"] = self.clock_domain(s.clock_domain_id)
        else:
            d["verilog"] = {"module": comp["module"], "name": s.name}
            d["wave"] = self.wave_path(s.path)
        area = self.area(s.area_id)
        if area:
            d["area"] = area
        if s.is_reg:
            d["clock_domain"] = self.clock_domain(s.clock_domain_id)
            d["reset_value"] = s.reset_value
        if s.clock_role:
            d["clock_role"] = s.clock_role
        if s.generated:
            d["generated"] = True
        if s.pruned:
            d["pruned"] = True
        d["loc"] = loc(s.file, s.line)
        return d

    # ------------------------------------------------------------------ names
    def normalize(self, name: str) -> str:
        s = name.strip().replace("/", ".")
        s = re.sub(r"\[(\d+):(\d+)\]$", "", s)          # waveform bit range suffix
        s = re.sub(r"\[(\d+)\]", r".\1", s)              # Verilog/waveform index
        s = re.sub(r"\((\d+)\)", r".\1", s)              # Spinal Vec apply
        s = re.sub(r"\.+", ".", s).strip(".")
        if s.startswith("TOP."):
            s = s[4:]
        if self.top and (s == self.top or s.startswith(self.top + ".")):
            s = s[len(self.top) + 1:]
        return s

    def component_by_path(self, path: str) -> dict | None:
        p = self.normalize(path) if path else ""
        r = self.conn.execute("SELECT id FROM components WHERE path = ?", (p,)).fetchone()
        return self.component(r[0]) if r else None

    def resolve_component(self, path: str | None) -> dict:
        if not path:
            return self.component(self.q("SELECT id FROM components WHERE parent_id IS NULL")[0][0])
        c = self.component_by_path(path)
        if c:
            return c
        p = self.normalize(path)
        rows = self.q("SELECT id, path FROM components WHERE path LIKE ? ESCAPE '\\' OR module = ? OR name = ? LIMIT 50",
                      ("%." + _like(p), p, p))
        if not rows:  # instance names may carry Spinal's `_<n>` dedup suffix (`lsu` is `tile.lsu_1`)
            qs = p.split(".")
            pats = [re.compile(rf"^{re.escape(q)}(_\d+)?$") for q in qs]
            for cid, cpath in self.q("SELECT id, path FROM components WHERE path != ''"):
                ps = cpath.split(".")
                if len(ps) >= len(qs) and all(pt.match(x) for pt, x in zip(pats, ps[len(ps) - len(qs):])):
                    rows.append((cid, cpath))
        if len(rows) == 1:
            return self.component(rows[0][0])
        if not rows:
            raise QueryError(f"no component {path!r}")
        raise QueryError(f"component {path!r} is ambiguous ({len(rows)} matches)", [r[1] for r in rows])

    def resolve(self, name: str, *, allow_group: bool = False, include_pruned: bool = False) -> list[Signal]:
        """Signals named by `name`: exactly one, or (with `allow_group`) a bundle/Area group."""
        s = self.normalize(name)
        live = "" if include_pruned else " AND s.pruned = 0"

        def one(where, args):
            rows = self.signals_where(where + live, args, limit=200)
            return rows

        for where, args in (("s.path = ?", (s,)), ("s.spinal_path = ?", (s,))):
            rows = one(where, args)
            if len(rows) == 1:
                return rows
            if len(rows) > 1:
                # Several signals share this path (BOOM: a RegNext of a bundle and its `_1` twin both get
                # the Spinal path `...regNext.br_mask`). Never pick one silently.
                if allow_group:
                    return rows
                raise QueryError(f"{name!r} names {len(rows)} signals; use one of their RTL paths",
                                 sorted(r.path for r in rows)[:30])
        # component prefix + Verilog name written with dots (`rob.io.enq_valids_0`)
        parts = s.split(".")
        for i in range(len(parts) - 1, -1, -1):
            comp = ".".join(parts[:i])
            r = self.conn.execute("SELECT id FROM components WHERE path = ?", (comp,)).fetchone()
            if r and i < len(parts):
                vname = "_".join(parts[i:])
                rows = one("s.component_id = ? AND s.name = ?", (r[0], vname))
                if len(rows) == 1:
                    return rows
                if rows:
                    break
        # Module.name for a module with one instance
        if len(parts) >= 2:
            rows = self.q("SELECT id FROM components WHERE module = ?", (parts[0],))
            if len(rows) == 1:
                rest = self.signals_where("s.component_id = ? AND (s.name = ? OR s.spinal_path LIKE ? ESCAPE '\\')" + live,
                                          (rows[0][0], "_".join(parts[1:]), "%." + _like(".".join(parts[1:]))))
                if len(rest) == 1:
                    return rest
        # bundle / Area group
        group = one("(s.spinal_path LIKE ? ESCAPE '\\' OR s.path LIKE ? ESCAPE '\\') AND s.kind != 'mem'",
                    (_like(s) + ".%", _like(s) + "\\_%"))
        if group:
            if allow_group:
                return self.signals_where("(s.spinal_path LIKE ? ESCAPE '\\' OR s.path LIKE ? ESCAPE '\\')" + live,
                                          (_like(s) + ".%", _like(s) + "\\_%"))
            raise QueryError(f"{name!r} is a group of signals (bundle or Area), not one signal; "
                             f"use a field, or a command that accepts interfaces (fanin, fanout, path)",
                             sorted({g.path for g in group})[:30])
        # unique suffix, most specific first: Verilog name, path/Spinal-path suffix, then a fuzzy
        # suffix whose instance names may carry Spinal's dedup suffix (`rob` matches `rob_1`).
        candidates: list[Signal] = []
        tiers = []
        if "." not in s:
            tiers.append(("s.name = ?", (s,)))
        tiers.append(("(s.path LIKE ? ESCAPE '\\' OR s.spinal_path LIKE ? ESCAPE '\\')", ("%." + _like(s), "%." + _like(s))))
        # Several matches are ambiguous even when only one of them is a named (not generated) signal:
        # `_zz_4` names 20 signals in BOOM small, one of them not flagged generated.
        for where, args in tiers:
            rows = one(where, args)
            if len(rows) == 1:
                return rows
            candidates += rows
            if rows:
                break
        if not candidates and "." in s:
            fuzzy = self._fuzzy(parts, live)
            if len(fuzzy) == 1:
                return fuzzy
            candidates += fuzzy
        if candidates:
            uniq = sorted({r.path for r in candidates})
            raise QueryError(f"{name!r} is ambiguous ({len(uniq)}{'+' if len(candidates) >= 200 else ''} matches); "
                             f"give more of the path", uniq[:30])
        if not include_pruned:
            pruned = self.signals_where("(s.path = ? OR s.spinal_path = ?) AND s.pruned = 1", (s, s))
            if pruned:
                raise QueryError(f"{name!r} was pruned by Spinal (unused or constant); it is not in the hardware")
        raise QueryError(f"no signal {name!r}" + (f" (normalized: {s!r})" if s != name else ""))

    def _fuzzy(self, parts: list[str], live: str) -> list[Signal]:
        """Signals whose path or Spinal path ends with `parts`, where each instance segment may also
        match with a `_<n>` suffix and the leaf may be written Verilog-style or Spinal-style."""
        leaf_variants = {parts[-1]}
        rows = []
        for i in range(1, len(parts)):
            leaf_variants.add("_".join(parts[i:]))
        for leaf in leaf_variants:
            rows += self.signals_where("(s.name = ? OR s.spinal_path LIKE ? ESCAPE '\\')" + live, (leaf, "%." + _like(leaf)),
                                       limit=5000)
        seg = lambda q: re.compile(rf"^{re.escape(q)}(_\d+)?$")  # noqa: E731
        out, seen = [], set()
        for r in rows:
            for full in (r.path, r.spinal_path):
                ps = full.split(".") if full else []
                for nleaf in range(1, len(parts) + 1):
                    qinst, qleaf = parts[:-nleaf] if nleaf < len(parts) + 1 else [], "_".join(parts[-nleaf:])
                    ok = bool(ps) and (ps[-1] == qleaf or ".".join(ps[-nleaf:]) == ".".join(parts[-nleaf:]))
                    if not ok:
                        continue
                    rest = ps[:-1] if ps[-1] == qleaf else ps[:-nleaf]
                    if len(qinst) <= len(rest) and all(seg(q).match(p) for q, p in zip(qinst, rest[len(rest) - len(qinst):])):
                        if r.id not in seen:
                            seen.add(r.id)
                            out.append(r)
                        break
        return out

    def resolve_one(self, name: str) -> Signal:
        return self.resolve(name)[0]


def _like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def loc(file: str | None, line: int | None) -> str | None:
    if not file:
        return None
    return f"{file}:{line}" if line else file
