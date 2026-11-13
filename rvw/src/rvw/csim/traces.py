"""Trace converters into `rvw.csim-trace/1`.

Inputs: C2 RVFI traces (`rvfi.jsonl`), CBP 2016 BT9 branch traces, and the legacy
`rvw.branch-trace/1`. ChampSim binary traces are read by the engine directly
(`--format champsim`); this module only decompresses them.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import lzma
import shutil
from pathlib import Path

from rvw.common.riscv import decode

HEADER = "rvw.csim-trace/1"
LINK = (1, 5)


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    if path.suffix == ".xz":
        return lzma.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def _hex(v) -> int:
    if isinstance(v, int):
        return v
    if not isinstance(v, str) or not v.startswith("0x"):
        raise ValueError(f"expected hex string, got {v!r}")
    return int(v, 16)


def branch_kind(insn: int, rd: int, xlen: int = 64) -> str | None:
    """Classify a control-transfer instruction with the RISC-V return-address hints."""
    d = decode(insn, xlen)
    m = d.mnemonic
    if d.cls == "branch":
        return "cond"
    if m in ("jal", "c.j", "c.jal"):
        if m == "c.jal":
            return "call"
        return "call" if rd in LINK else "jump"
    if m in ("jalr", "c.jr", "c.jalr"):
        rs1 = d.rs1[1] if d.rs1 else 0
        rd_link, rs1_link = rd in LINK, rs1 in LINK
        if m == "c.jalr":
            rd_link = True
        if not rd_link:
            return "ret" if rs1_link else "ijump"
        return "icall"  # push (a coroutine swap, rd != rs1 both links, is also treated as a push)
    return None


def _flags(insn: int, xlen: int) -> str:
    """l: load; m: register move (mv, c.mv); z: zero idiom (li rd,0; xor/sub rd,rs,rs)."""
    d = decode(insn, xlen)
    m, f = d.mnemonic, ""
    if d.cls == "load":
        f += "l"
    rs1 = (insn >> 15) & 31
    if m == "c.mv" or (m == "addi" and (insn >> 20) == 0 and rs1 != 0):
        f += "m"
    if (m == "addi" and (insn >> 20) == 0 and rs1 == 0) or \
            (m == "c.li" and ((insn >> 2) & 31) == 0 and not (insn >> 12) & 1) or \
            (m in ("xor", "sub") and d.rs1 is not None and d.rs1 == d.rs2):
        f += "z"
    return f or "-"


def from_c2(src: Path, dst: Path, values: bool = False) -> dict:
    """Convert one single-hart C2 trace. Trapped instructions get no branch row."""
    src, dst = Path(src), Path(dst)
    count = traps = branches = mem = 0
    xlen = 64
    first_order = None
    prev_order = None
    with _open_text(src) as stream, dst.open("x") as out:
        header = json.loads(stream.readline())
        if not str(header.get("schema", "")).startswith("rvw.rvfi/"):
            raise ValueError("not a C2 trace (missing rvw.rvfi header)")
        if header.get("harts") and len(header["harts"]) > 1:
            raise ValueError("multi-hart C2 traces are unsupported")
        xlen = int(header.get("xlen", 64))
        out.write(HEADER + "\n")
        out.write(f"# source=c2 elf={header.get('elf', '')} core={header.get('core', '')}\n")
        for line in stream:
            if not line.strip():
                continue
            r = json.loads(line)
            if "event" in r:
                continue
            if "hart" in r and r["hart"] not in (0, "0"):
                raise ValueError("multi-hart C2 traces are unsupported")
            order = int(r["order"])
            if prev_order is not None and order != prev_order + 1:
                raise ValueError(f"C2 order gap at {order}")
            prev_order = order
            if first_order is None:
                first_order = order
            count += 1
            ordinal = order - first_order + 1
            pc, nxt, insn = _hex(r["pc"]), _hex(r["pc_next"]), _hex(r["insn"])
            if r.get("trap"):
                traps += 1
                continue
            length = 4 if insn & 3 == 3 else 2
            rd = int(r.get("rd", 0))
            kind = branch_kind(insn, rd, xlen)
            rmask, wmask = int(r.get("mem_rmask", 0)), int(r.get("mem_wmask", 0))
            if rmask:
                out.write(f"L {ordinal} {pc:x} {_hex(r['mem_addr']):x} {bin(rmask).count('1')}\n"); mem += 1
            if wmask:
                out.write(f"S {ordinal} {pc:x} {_hex(r['mem_addr']):x} {bin(wmask).count('1')}\n"); mem += 1
            if values and rd:
                out.write(f"W {ordinal} {pc:x} {rd} {_hex(r['rd_wdata']):x} {_flags(insn, xlen)}\n")
            if kind:
                fall = pc + length
                taken = nxt != fall if kind == "cond" else True
                out.write(f"B {ordinal} {pc:x} {kind} {int(taken)} {nxt:x} {length}\n")
                branches += 1
        if not count:
            raise ValueError("empty C2 trace")
        out.write(f"END {count}\n")
    return {"format": "c2", "instructions": count, "branches": branches, "memory_rows": mem, "traps_skipped": traps}


_BT9_KIND = {("JMP", "DIR", "CND"): "cond", ("JMP", "IND", "CND"): "cond",
             ("JMP", "DIR", "UCD"): "jump", ("JMP", "IND", "UCD"): "ijump",
             ("CALL", "DIR", "UCD"): "call", ("CALL", "IND", "UCD"): "icall",
             ("CALL", "DIR", "CND"): "call", ("CALL", "IND", "CND"): "icall",
             ("RET", "IND", "UCD"): "ret", ("RET", "DIR", "UCD"): "ret", ("RET", "IND", "CND"): "ret"}


def from_bt9(src: Path, dst: Path) -> dict:
    """Convert a CBP 2016 BT9 trace (nodes, edges, edge sequence). Edge `inst_cnt` counts
    the non-branch instructions between the source and destination branches."""
    src, dst = Path(src), Path(dst)
    nodes: dict[int, tuple[int, str, int]] = {}
    edges: dict[int, tuple[int, int, bool, int, int]] = {}
    section = None
    count = branches = 0
    unsupported = 0
    with _open_text(src) as stream, dst.open("x") as out:
        first = stream.readline().strip()
        if not first.startswith("BT9_SPA_TRACE_FORMAT"):
            raise ValueError("not a BT9 trace")
        out.write(HEADER + "\n# source=bt9\n")
        for line in stream:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s in ("BT9_NODES", "BT9_EDGES", "BT9_EDGE_SEQUENCE"):
                section = s
                continue
            if s == "EOF":
                break
            f = s.split()
            if section == "BT9_NODES" and f[0] == "NODE":
                nid, va = int(f[1]), int(f[2], 16) if f[2].startswith("0x") else int(f[2])
                size = int(f[5]) if len(f) > 5 and f[5].isdigit() else 4
                cls = ""
                if "class:" in f:
                    cls = f[f.index("class:") + 1]
                nodes[nid] = (va, cls, size)
            elif section == "BT9_EDGES" and f[0] == "EDGE":
                eid, srcn, dstn = int(f[1]), int(f[2]), int(f[3])
                taken = f[4] == "T"
                tgt = int(f[5], 16) if f[5].startswith("0x") else int(f[5])
                inst = int(f[7])
                edges[eid] = (srcn, dstn, taken, tgt, inst)
            elif section == "BT9_EDGE_SEQUENCE":
                srcn, dstn, taken, tgt, inst = edges[int(f[0])]
                node = nodes.get(srcn)
                if node is None or not node[1]:
                    count += inst
                    continue  # the start node carries no branch
                count += 1
                ordinal = count
                count += inst
                parts = tuple(node[1].split("+"))
                kind = _BT9_KIND.get(parts[:3])
                if kind is None:
                    unsupported += 1
                    continue
                if kind != "cond" and not taken:
                    kind = "cond"  # conditional call/return not taken: direction only
                out.write(f"B {ordinal} {node[0]:x} {kind} {int(taken)} {tgt if taken else 0:x} {node[2] if node[2] < 16 else 4}\n")
                branches += 1
        if not count:
            raise ValueError("empty BT9 trace")
        out.write(f"END {count}\n")
    return {"format": "bt9", "instructions": count, "branches": branches, "unsupported_branch_classes": unsupported}


def decompress(src: Path, dst_dir: Path) -> Path:
    """Return an uncompressed path for a ChampSim trace (.xz/.gz are expanded)."""
    src = Path(src)
    if src.suffix not in (".xz", ".gz"):
        return src
    out = Path(dst_dir) / src.stem
    opener = lzma.open if src.suffix == ".xz" else gzip.open
    with opener(src, "rb") as i, out.open("wb") as o:
        shutil.copyfileobj(i, o, 1 << 20)
    return out


def detect(path: Path) -> str:
    """Guess the trace format from content: csim, branch, c2, bt9 or champsim."""
    path = Path(path)
    try:
        with _open_text(path) as s:
            head = s.readline(256)
    except (UnicodeDecodeError, OSError, EOFError, lzma.LZMAError):
        return "champsim"
    if head.startswith(HEADER):
        return "csim"
    if head.startswith("rvw.branch-trace/1"):
        return "branch"
    if head.startswith("BT9_SPA_TRACE_FORMAT"):
        return "bt9"
    if head.lstrip().startswith("{") and "rvw.rvfi" in head:
        return "c2"
    return "champsim"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
