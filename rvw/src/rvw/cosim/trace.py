"""Validate and stream the shared C2 JSONL format."""
import json
import re
from rvw.common.riscv import integer_sources
from rvw.common.riscv import decode

HEX = "pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata".split()
INT = "order cycle mode rs1 rs2 rd mem_rmask mem_wmask".split()
BOOL = "trap intr halt mem_fault".split()


def hexnum(value, width=64):
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-f]+", value):
        raise ValueError(f"C2 expects lowercase hex string, got {value!r}")
    n = int(value, 16)
    if n >= 1 << width:
        raise ValueError(f"C2 value exceeds {width} bits")
    return n


class Trace:
    def __init__(self, path):
        self.file = path if hasattr(path, "readline") else open(path)
        try:
            self.header = json.loads(next(self.file))
            h = self.header
            if not isinstance(h, dict) or h.get("schema") not in ("rvw.rvfi/1", "rvw.rvfi/2") or h.get("xlen") not in (32, 64):
                raise ValueError("expected rvw.rvfi/1 header with xlen 32 or 64")
            self.multihart = "harts" in h
            caps = h.get("capabilities", ["multihart"] if self.multihart else ["state"])
            if not isinstance(caps, list) or not caps or any(c not in ("state", "multihart") for c in caps) or len(set(caps)) != len(caps):
                raise ValueError("invalid C2 capabilities")
            self.state = "state" in caps
            if self.multihart != ("multihart" in caps) or (self.multihart and h["schema"] != "rvw.rvfi/2"):
                raise ValueError("multi-hart capability requires C2/2 harts")
            if self.multihart:
                hs = h["harts"]
                if not isinstance(hs, list) or not hs or any(type(v) is not int or v < 0 for v in hs) or len(set(hs)) != len(hs):
                    raise ValueError("invalid harts")
            csrs = h.get("csr_snapshot", [])
            if not isinstance(csrs, list) or len(set(csrs)) != len(csrs):
                raise ValueError("csr_snapshot must be a unique address list")
            for address in csrs:
                hexnum(address, 12)
            if csrs and h["schema"] != "rvw.rvfi/2":
                raise ValueError("CSR snapshots require rvw.rvfi/2")
            for k in ("isa", "core", "config", "elf"):
                if not isinstance(h.get(k), str):
                    raise ValueError(f"missing or invalid C2 header {k}")
        except BaseException:
            self.file.close()
            raise

    def __iter__(self):
        order, cycle, ended = -1, -1, False
        xlen = self.header["xlen"]
        epochs, orders, done, ids = {}, {}, set(), set()
        capture = 0
        for line, text in enumerate(self.file, 2):
            try:
                obj = json.loads(text)
                if not isinstance(obj, dict):
                    raise ValueError("record must be an object")
                if ended:
                    raise ValueError("record after end event")
                if type(obj.get("cycle")) is not int or obj["cycle"] < 0 or obj["cycle"] < cycle:
                    raise ValueError("invalid or decreasing cycle")
                cycle = obj["cycle"]
                if self.multihart:
                    def decimal(v):
                        if not isinstance(v, str) or not re.fullmatch(r"0|[1-9][0-9]*", v):
                            raise ValueError("expected canonical decimal string")
                        return int(v)
                    if cycle > 9007199254740991 or decimal(obj.get("capture_seq")) != capture:
                        raise ValueError("invalid capture sequence or cycle")
                    capture += 1
                    if obj.get("event") != "external":
                        h, ep = obj.get("hart"), obj.get("epoch")
                        if type(h) is not int or h not in self.header["harts"] or type(ep) is not int or h in done:
                            raise ValueError("invalid or completed hart")
                        if obj.get("event") == "reset":
                            if ep != epochs.get(h, -1) + 1:
                                raise ValueError("invalid reset epoch")
                            epochs[h], orders[h] = ep, -1
                        elif epochs.get(h) != ep:
                            raise ValueError("missing reset or invalid epoch")
                        if "event" not in obj:
                            obj["order"] = decimal(obj.get("order"))
                            if obj["order"] >= 1 << 64:
                                raise ValueError("order exceeds 64 bits")
                            order = orders[h]
                elif any(k in obj for k in ("hart", "epoch", "capture_seq")):
                    raise ValueError("multi-hart fields require harts")
                if "event" in obj:
                    if self.multihart and obj["event"] == "reset":
                        pass
                    elif self.multihart and obj["event"] == "hart_end":
                        if obj.get("status") not in ("pass", "fail", "error", "timeout", "assert", "rvfi_error"):
                            raise ValueError("invalid hart status")
                        done.add(h)
                    elif self.multihart and obj["event"] == "external":
                        if not isinstance(obj.get("id"), str) or not obj["id"] or obj["id"] in ids or obj.get("action") not in ("read", "write", "atomic", "irq", "maintenance"):
                            raise ValueError("invalid external event")
                        ids.add(obj["id"])
                        if "source" not in obj:
                            raise ValueError("missing external source")
                        for key in ("address", "data", "mask"):
                            hexnum(obj[key], xlen)
                    elif obj["event"] == "trap":
                        obj["cause"] = hexnum(obj["cause"], xlen)
                        obj["tval"] = hexnum(obj["tval"], xlen)
                        if type(obj.get("intr")) is not bool:
                            raise ValueError("trap event intr must be boolean")
                        if bool(obj["cause"] >> (xlen-1)) != obj["intr"]:
                            raise ValueError("trap cause interrupt bit and intr disagree")
                    elif obj["event"] == "irq":
                        obj["levels"] = hexnum(obj["levels"], xlen)
                    elif obj["event"] == "end":
                        if not isinstance(obj.get("status"), str):
                            raise ValueError("end event requires status")
                        ended = True
                    else:
                        raise ValueError(f"unknown C2 event {obj['event']!r}")
                else:
                    for k in HEX:
                        obj[k] = hexnum(obj[k], 32 if k == "insn" else xlen)
                    for k in INT:
                        if type(obj[k]) is not int or obj[k] < 0:
                            raise ValueError(f"invalid nonnegative integer {k}")
                    for k in BOOL:
                        if type(obj[k]) is not bool:
                            raise ValueError(f"invalid boolean {k}")
                    if obj["order"] != order+1:
                        raise ValueError("instruction orders must start at zero with no gaps")
                    order = obj["order"]
                    if self.multihart:
                        orders[h] = order
                    if obj["mode"] not in (0, 1, 3):
                        raise ValueError("invalid privilege mode")
                    if any(obj[k] > 31 for k in ("rs1", "rs2", "rd")):
                        raise ValueError("register index exceeds 31")
                    if any(obj[k] >= 1 << (xlen//8) for k in ("mem_rmask", "mem_wmask")):
                        raise ValueError("memory mask exceeds XLEN bytes")
                if "event" not in obj and self.header["schema"] == "rvw.rvfi/2" and self.state:
                    if type(obj.get("fd_valid")) is not bool:
                        raise ValueError("fd_valid must be boolean")
                    if type(obj.get("fd")) is not int or not 0 <= obj["fd"] < 32:
                        raise ValueError("invalid FP destination")
                    obj["fd_wdata"] = hexnum(obj["fd_wdata"], 64)
                    for key, width in (("fflags", 5), ("fcsr", 8)):
                        obj[key] = hexnum(obj[key], width)
                    if obj["fflags"] != obj["fcsr"] & 31:
                        raise ValueError("fflags and fcsr disagree")
                elif "event" not in obj and any(k in obj for k in ("fd_valid", "fd_wdata", "fflags", "fcsr")):
                    raise ValueError("FP fields require rvw.rvfi/2")
                if "event" not in obj:
                    snapshots = obj.get("csr_state", {})
                    if not isinstance(snapshots, dict) or set(snapshots) != set(self.header.get("csr_snapshot", [])):
                        raise ValueError("csr_state must contain exactly the declared snapshot addresses")
                    obj["csr_state"] = {k: hexnum(v, xlen) for k, v in snapshots.items()}
                if "fault_access" in obj:
                    if self.header["schema"] != "rvw.rvfi/2" or "event" in obj or not obj["trap"]:
                        raise ValueError("fault_access requires a version 2 trap instruction")
                    access = obj["fault_access"]
                    keys = {"addr", "rmask", "wmask", "completed_rmask", "completed_wmask", "rdata", "wdata"}
                    if not isinstance(access, dict) or set(access) != keys:
                        raise ValueError("invalid fault_access fields")
                    access["addr"] = hexnum(access["addr"], xlen)
                    for key in ("rmask", "wmask", "completed_rmask", "completed_wmask"):
                        if type(access[key]) is not int or not 0 <= access[key] < 1 << (xlen//8):
                            raise ValueError("invalid fault-access mask")
                    for direction in ("r", "w"):
                        completed = access[f"completed_{direction}mask"]
                        if completed & ~access[f"{direction}mask"]:
                            raise ValueError("completed mask exceeds attempted mask")
                        data = access[f"{direction}data"]
                        if completed:
                            access[f"{direction}data"] = hexnum(data, xlen)
                        elif data is not None:
                            raise ValueError("uncompleted access data must be null")
                yield obj
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"C2 line {line}: {exc}") from exc

    def close(self):
        self.file.close()


def record(effect, order, cycle=None, intr=False, xlen=64):
    """Serialize an independently executed reference instruction to C2."""
    if not effect['trap'] and decode(effect['insn'], xlen).mnemonic == 'unknown':
        raise ValueError(f"unknown source operands for successful instruction {effect['insn']:#x}")
    result = {k: hex(effect[k]) for k in HEX if k in effect}
    rs1, rs2 = integer_sources(effect["insn"], xlen)
    before = effect["before"]
    result.update(rs1=rs1, rs2=rs2, rs1_rdata=hex(before[rs1]), rs2_rdata=hex(before[rs2]),
                  order=order, cycle=order if cycle is None else cycle,
                  mode=effect["mode"], rd=effect["rd"],
                  mem_rmask=effect["mem_rmask"], mem_wmask=effect["mem_wmask"],
                  trap=bool(effect["trap"]), intr=intr, halt=False,
                  mem_fault=bool(effect["mem_fault"]))
    return result
