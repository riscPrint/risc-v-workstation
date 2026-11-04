"""Bounded TestRIG RVFI-DII v1 transport, independent of ELF/C2 adapters."""
from dataclasses import dataclass, astuple
import math
import socket
import struct
import time
from typing import Protocol

INSTRUCTION = struct.Struct("<IHBB")
EXECUTION = struct.Struct("<10Q8B")
MAX_TOKENS = 65536


@dataclass(frozen=True)
class Token:
    insn: int = 0
    time: int = 1
    cmd: int = 1

    def encode(self):
        if self.cmd not in (0, 1):
            raise ValueError("unsupported DII command")
        return INSTRUCTION.pack(self.insn, self.time, self.cmd, 0)

    @classmethod
    def decode(cls, data):
        insn, tick, cmd, padding = INSTRUCTION.unpack(data)
        if padding or cmd not in (0, 1):
            raise ValueError("invalid DII padding or command")
        return cls(insn, tick, cmd)


@dataclass(frozen=True)
class Retirement:
    order: int = 0
    pc_rdata: int = 0
    pc_wdata: int = 0
    insn: int = 0
    rs1_rdata: int = 0
    rs2_rdata: int = 0
    rd_wdata: int = 0
    mem_addr: int = 0
    mem_rdata: int = 0
    mem_wdata: int = 0
    mem_rmask: int = 0
    mem_wmask: int = 0
    rs1_addr: int = 0
    rs2_addr: int = 0
    rd_addr: int = 0
    trap: int = 0
    halt: int = 0
    intr: int = 0

    def encode(self):
        if any(x not in (0, 1) for x in (self.trap, self.halt, self.intr)):
            raise ValueError("unsupported RVFI flags or trace version")
        if any(x > 31 for x in (self.rs1_addr, self.rs2_addr, self.rd_addr)):
            raise ValueError("invalid register address")
        return EXECUTION.pack(*astuple(self))

    @classmethod
    def decode(cls, data):
        packet = cls(*EXECUTION.unpack(data))
        packet.encode()
        return packet


class Hook(Protocol):
    """Core-owned hook. execute must honor timing and drain in retirement order.

    reset clears GPRs, CSRs and 64 KiB memory and sets PC to 0x80000000.
    execute returns retirement packets without the terminal halt packet.
    The timeout argument bounds execution, including stalls and drain.
    """
    def reset(self) -> None: ...
    def execute(self, tokens: list[Token], timeout: float) -> list[Retirement]: ...


def deadline(timeout):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    return time.monotonic() + timeout


def remaining(end):
    left = end - time.monotonic()
    if left <= 0:
        raise TimeoutError("DII stream deadline")
    return left


def receive(sock, count, end):
    data = bytearray()
    while len(data) < count:
        sock.settimeout(remaining(end))
        part = sock.recv(count - len(data))
        if not part:
            raise EOFError("truncated DII stream")
        data.extend(part)
    return bytes(data)


def send(sock, data, end):
    sock.settimeout(remaining(end))
    sock.sendall(data)


def serve_connection(sock, hook: Hook, *, timeout=30, max_streams=1000):
    """Serve a vengine TCP connection. Negotiate v1 with current QCVEngine.

    Each EndOfTrace executes the buffered stream, resets the hook and sends
    a halt delimiter. EOF or a deadline aborts the session and resets the hook.
    No equivalence verdict is produced here.
    """
    if max_streams < 1:
        raise ValueError("max_streams must be positive")
    hook.reset()
    try:
        for _ in range(max_streams):
            end = deadline(timeout)
            tokens = []
            while True:
                token = Token.decode(receive(sock, INSTRUCTION.size, end))
                if token.cmd == 0:
                    break
                if len(tokens) >= MAX_TOKENS:
                    raise ValueError("DII token limit")
                tokens.append(token)
            # VERS is backwards-compatible negotiation: an empty v1 halt.
            if token.insn not in (0, 0x56455253) or (token.insn and tokens):
                raise ValueError("unsupported EndOfTrace payload")
            packets = hook.execute(tokens, remaining(end)) if tokens else []
            if len(packets) > len(tokens):
                raise ValueError("more retirements than injected tokens")
            previous = None
            for packet in packets:
                if packet.halt or (previous is not None and packet.order <= previous):
                    raise ValueError("invalid retirement order or premature halt")
                send(sock, packet.encode(), end)
                previous = packet.order
            hook.reset()
            send(sock, Retirement(halt=1).encode(), end)
    finally:
        hook.reset()


def exchange(sock, tokens, *, timeout=30):
    """Run one stream against a v1 server (Sail or a core hook)."""
    if not tokens or len(tokens) > MAX_TOKENS or any(t.cmd != 1 for t in tokens):
        raise ValueError("expected a bounded nonempty instruction stream")
    end = deadline(timeout)
    send(sock, b"".join(t.encode() for t in tokens) + Token(cmd=0).encode(), end)
    result = []
    while len(result) <= len(tokens):
        packet = Retirement.decode(receive(sock, EXECUTION.size, end))
        if packet.halt:
            return result
        if result and packet.order <= result[-1].order:
            raise ValueError("non-increasing retirement order")
        result.append(packet)
    raise ValueError("missing halt or excess retirements")


def compare(core, sail, tokens, *, timeout=30):
    """Strict v1 replay. Short, empty or malformed traces cannot match."""
    dut = exchange(core, tokens, timeout=timeout)
    reference = exchange(sail, tokens, timeout=timeout)
    if len(dut) != len(tokens) or len(reference) != len(tokens):
        return {"status": "inconclusive", "cause": "incomplete_stream",
                "core_retired": len(dut), "sail_retired": len(reference)}
    for index, token in enumerate(tokens):
        mask = 0xffffffff if token.insn & 3 == 3 else 0xffff
        if any(packets[index].insn != token.insn & mask for packets in (dut, reference)):
            return {"status": "inconclusive", "cause": "injection_mismatch", "index": index}
    for index, (actual, expected) in enumerate(zip(dut, reference)):
        differences = {name: [getattr(actual, name), getattr(expected, name)]
                       for name in actual.__dataclass_fields__
                       if getattr(actual, name) != getattr(expected, name)}
        if differences:
            return {"status": "mismatch", "index": index, "differences": differences}
    return {"status": "match", "instructions": len(dut), "trace_complete": True}
