"""Minimal ELF reader/patcher: symbols, and rewriting the value of an integer data symbol.

Used by `rvw reduce --symbol` to shrink program parameters (iteration counts, sizes) stored in
initialized data. Standard library only; ELF32/ELF64, little endian.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class Symbol:
    name: str
    value: int
    size: int
    shndx: int


class Elf:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            self.data = bytearray(f.read())
        d = self.data
        if d[:4] != b"\x7fELF":
            raise ValueError(f"{path}: not an ELF file")
        self.is64 = d[4] == 2
        if d[5] != 1:
            raise ValueError(f"{path}: big-endian ELF not supported")
        if self.is64:
            (self.phoff, self.shoff) = struct.unpack_from("<QQ", d, 0x20)
            (self.phentsize, self.phnum, self.shentsize, self.shnum, self.shstrndx) = struct.unpack_from("<HHHHH", d, 0x36)
        else:
            (self.phoff, self.shoff) = struct.unpack_from("<II", d, 0x1C)
            (self.phentsize, self.phnum, self.shentsize, self.shnum, self.shstrndx) = struct.unpack_from("<HHHHH", d, 0x2A)
        self.sections = [self._sh(i) for i in range(self.shnum)]
        self.segments = [self._ph(i) for i in range(self.phnum)]

    def _sh(self, i):
        o = self.shoff + i * self.shentsize
        if self.is64:
            name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from("<IIQQQQIIQQ", self.data, o)
        else:
            name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from("<IIIIIIIIII", self.data, o)
        return dict(name=name, type=typ, addr=addr, off=off, size=size, link=link, entsize=entsize)

    def _ph(self, i):
        o = self.phoff + i * self.phentsize
        if self.is64:
            typ, flags, off, vaddr, paddr, filesz, memsz, align = struct.unpack_from("<IIQQQQQQ", self.data, o)
        else:
            typ, off, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from("<IIIIIIII", self.data, o)
        return dict(type=typ, off=off, vaddr=vaddr, paddr=paddr, filesz=filesz)

    def _str(self, sec, off):
        s = self.sections[sec]["off"] + off
        e = self.data.index(b"\0", s)
        return self.data[s:e].decode(errors="replace")

    def symbols(self) -> dict[str, Symbol]:
        out = {}
        for s in self.sections:
            if s["type"] != 2:   # SHT_SYMTAB
                continue
            ent = s["entsize"] or (24 if self.is64 else 16)
            for k in range(s["size"] // ent):
                o = s["off"] + k * ent
                if self.is64:
                    name, info, other, shndx, value, size = struct.unpack_from("<IBBHQQ", self.data, o)
                else:
                    name, value, size, info, other, shndx = struct.unpack_from("<IIIBBH", self.data, o)
                n = self._str(s["link"], name) if name else ""
                if n:
                    out[n] = Symbol(n, value, size, shndx)
        return out

    def file_offset(self, vaddr: int) -> int | None:
        for p in self.segments:
            if p["type"] == 1 and p["vaddr"] <= vaddr < p["vaddr"] + p["filesz"]:
                return p["off"] + vaddr - p["vaddr"]
        return None

    def read_int(self, sym: str, size: int | None = None) -> int:
        s = self.symbols()[sym]
        n = size or s.size or 4
        o = self.file_offset(s.value)
        if o is None:
            raise ValueError(f"{sym} is not in initialized data (in .bss?)")
        return int.from_bytes(self.data[o:o + n], "little", signed=False)

    def write_int(self, sym: str, value: int, size: int | None = None) -> None:
        s = self.symbols()[sym]
        n = size or s.size or 4
        o = self.file_offset(s.value)
        if o is None:
            raise ValueError(f"{sym} is not in initialized data (in .bss?)")
        self.data[o:o + n] = int(value).to_bytes(n, "little", signed=False)

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.data)
