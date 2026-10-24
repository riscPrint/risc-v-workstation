"""Small, bounded ELF reader for load segments and optional tohost symbol."""
import struct
from pathlib import Path


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        d = self.data
        if len(d) < 64 or d[:4] != b"\x7fELF" or d[5] != 1 or d[4] not in (1, 2):
            raise ValueError("expected a little-endian ELF32 or ELF64 file")
        self.xlen = 64 if d[4] == 2 else 32
        f = "<HHIQQQIHHHHHH" if self.xlen == 64 else "<HHIIIIIHHHHHH"
        h = struct.unpack_from(f, d, 16)
        if h[1] != 243 or h[0] != 2:
            raise ValueError("expected a statically linked RISC-V executable ELF")
        self.entry, phoff, shoff = h[3:6]
        self.segments = []
        for i in range(h[9]):
            off = phoff + i * h[8]
            p = struct.unpack_from("<IIQQQQQQ" if self.xlen == 64 else "<IIIIIIII", d, off)
            if p[0] != 1:
                continue
            if self.xlen == 64:
                _, _, offset, va, pa, filesz, memsz, _ = p
            else:
                _, offset, va, pa, filesz, memsz, _, _ = p
            if filesz > memsz or offset + filesz > len(d):
                raise ValueError("invalid ELF load segment")
            self.segments.append((pa or va, d[offset:offset+filesz], memsz))
        if not self.segments:
            raise ValueError("ELF has no load segments")
        self.symbols = {}
        sections = [struct.unpack_from("<IIQQQQIIQQ" if self.xlen == 64 else "<IIIIIIIIII",
                                       d, shoff + i * h[10]) for i in range(h[11])]
        for s in sections:
            if s[1] != 2 or not s[9]:
                continue
            strings = sections[s[6]]
            names = d[strings[4]:strings[4]+strings[5]]
            for off in range(s[4], s[4]+s[5], s[9]):
                vals = struct.unpack_from("<IBBHQQ" if self.xlen == 64 else "<IIIBBH", d, off)
                name, value = vals[0], vals[4] if self.xlen == 64 else vals[1]
                end = names.find(b"\0", name)
                if end >= 0:
                    self.symbols[names[name:end].decode(errors="replace")] = value
