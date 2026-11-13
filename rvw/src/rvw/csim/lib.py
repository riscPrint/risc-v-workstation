"""In-process access to the native component models for timing models.

    from rvw.csim.lib import Components
    c = Components({"branch": {"model": "tage-sc-l"}, "btb": {"entries": 4096},
                    "memory": {"l1d": {"size_kib": 48, "ways": 12}}})
    t, taken = c.predict(pc)          # direction ticket and prediction
    c.history(pc, "cond", actual, target)  # actual-path history, right after predict
    c.update(t, actual)               # train later (delayed update is allowed)
    done = c.access(cycle, pc, addr)  # data access; returns the completion cycle

The configuration uses the study keys of `rvw.csim-study/1` (sections branch, btb,
ras, indirect, memory). Histories follow the actual path; a caller that models wrong
paths must not feed wrong-path branches to `history`.
"""
from __future__ import annotations

import ctypes
import json

from . import config as cfg
from . import engine

KINDS = {"cond": 1, "jump": 2, "ijump": 3, "call": 4, "icall": 5, "ret": 6}
_lib = None


def _load():
    global _lib
    if _lib is None:
        lib = ctypes.CDLL(str(engine.build("lib")))
        u64, vp, i = ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int
        sig = {
            "csim_create": (vp, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]),
            "csim_destroy": (None, [vp]),
            "csim_dir_predict": (u64, [vp, u64, ctypes.POINTER(i)]),
            "csim_dir_update": (i, [vp, u64, i]),
            "csim_dir_discard": (None, [vp, u64]),
            "csim_history": (None, [vp, u64, i, i, u64]),
            "csim_btb_lookup": (i, [vp, u64, ctypes.POINTER(u64)]),
            "csim_btb_update": (None, [vp, u64, i, i, u64]),
            "csim_ras_push": (None, [vp, u64]),
            "csim_ras_pop": (i, [vp, ctypes.POINTER(u64)]),
            "csim_ind_predict": (u64, [vp, u64, ctypes.POINTER(u64)]),
            "csim_ind_update": (i, [vp, u64, u64]),
            "csim_mem_access": (u64, [vp, u64, u64, u64, i, i]),
            "csim_reset_stats": (None, [vp]),
            "csim_stats": (ctypes.c_size_t, [vp, u64, ctypes.c_char_p, ctypes.c_size_t]),
        }
        for name, (res, args) in sig.items():
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = res, args
        _lib = lib
    return _lib


class Components:
    def __init__(self, study: dict):
        data = cfg.load(study)
        for k in ("frontend", "mdp", "vp", "lap", "wrong_path", "report"):
            if k in data:
                raise ValueError(f"section {k} is not available in-process; use rvw csim run")
        self._lib = _load()
        err = ctypes.create_string_buffer(512)
        self._h = self._lib.csim_create(cfg.to_kv(data).encode(), err, len(err))
        if not self._h:
            raise ValueError(err.value.decode())

    def close(self):
        if self._h:
            self._lib.csim_destroy(self._h)
            self._h = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def predict(self, pc: int) -> tuple[int, bool]:
        taken = ctypes.c_int(0)
        t = self._lib.csim_dir_predict(self._h, pc, ctypes.byref(taken))
        return t, bool(taken.value)

    def update(self, ticket: int, taken: bool) -> None:
        if ticket and self._lib.csim_dir_update(self._h, ticket, int(taken)) != 0:
            raise KeyError(f"unknown direction ticket {ticket}")

    def discard(self, ticket: int) -> None:
        self._lib.csim_dir_discard(self._h, ticket)

    def history(self, pc: int, kind: str, taken: bool, target: int) -> None:
        self._lib.csim_history(self._h, pc, KINDS[kind], int(taken), target)

    def btb_lookup(self, pc: int) -> tuple[int, int]:
        """(level or -1, target)."""
        t = ctypes.c_uint64(0)
        level = self._lib.csim_btb_lookup(self._h, pc, ctypes.byref(t))
        return level, t.value

    def btb_update(self, pc: int, kind: str, taken: bool, target: int) -> None:
        self._lib.csim_btb_update(self._h, pc, KINDS[kind], int(taken), target)

    def ras_push(self, addr: int) -> None:
        self._lib.csim_ras_push(self._h, addr)

    def ras_pop(self) -> int | None:
        a = ctypes.c_uint64(0)
        return a.value if self._lib.csim_ras_pop(self._h, ctypes.byref(a)) == 1 else None

    def indirect_predict(self, pc: int) -> tuple[int, int]:
        t = ctypes.c_uint64(0)
        ticket = self._lib.csim_ind_predict(self._h, pc, ctypes.byref(t))
        return ticket, t.value

    def indirect_update(self, ticket: int, target: int) -> None:
        if ticket:
            self._lib.csim_ind_update(self._h, ticket, target)

    def access(self, cycle: int, pc: int, addr: int, store: bool = False, fetch: bool = False) -> int:
        return self._lib.csim_mem_access(self._h, cycle, pc, addr, int(store), int(fetch))

    def reset_stats(self) -> None:
        self._lib.csim_reset_stats(self._h)

    def stats(self, instructions: int = 0) -> dict:
        n = self._lib.csim_stats(self._h, instructions, None, 0)
        buf = ctypes.create_string_buffer(n)
        self._lib.csim_stats(self._h, instructions, buf, n)
        return json.loads(buf.value.decode())
