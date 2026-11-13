"""Decoupled fetch/decode timing for the committed instruction path."""
from collections import Counter, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class FrontendConfig:
    fdip: bool = False
    decode_width: int = 4
    decode_entries: int = 32
    decode_latency: int = 1
    fetch_latency: int = 1
    ftq_entries: int = 16
    block_bytes: int = 32
    predictor_latency: int = 1
    uop_cache_entries: int = 0
    uop_cache_width: int = 6
    uop_cache_latency: int = 1

    def __post_init__(self):
        if type(self.fdip) is not bool:
            raise ValueError('frontend fdip must be boolean')
        for key, value in vars(self).items():
            if key == 'fdip':
                continue
            if type(value) is not int or value < (0 if key == 'uop_cache_entries' else 1):
                raise ValueError(f'frontend {key} must be a valid integer capacity or delay')
        if self.block_bytes & (self.block_bytes - 1):
            raise ValueError('frontend block_bytes must be a power of two')


class Frontend:
    """FIFO target queue and decoded blocks. No wrong-path bytes are available.

    A block is filled only after its last traced operation passes decode.
    FIFO replacement is deliberately fixed. Keys describe decoded operations.
    Self-modifying code and context changes are unsupported.
    """
    def __init__(self, config, fetch_width, fetch_entries):
        self.config = FrontendConfig(**config)
        self.width, self.capacity = fetch_width, fetch_entries
        self.fetch = deque()
        self.decoded = deque()
        self.cache = {}
        self.fills = {}
        self.blocked_until = 0
        self.events = Counter()
        self.position = 0
        self.predicted_position = 0
        self.targets = deque()

    def predict_target(self, cycle, instructions, memory):
        """One actual-path target per cycle, with bounded FTQ runahead."""
        if self.predicted_position >= len(instructions):
            return
        if len(self.targets) >= self.config.ftq_entries:
            self.events['fdip_ftq_full'] += 1
            return
        first = self.predicted_position
        end = first + 1
        while end < len(instructions):
            prev, op = instructions[end-1], instructions[end]
            if (prev.kind in ('branch', 'jump') or
                op.pc != prev.pc + prev.length or
                op.pc // self.config.block_bytes != instructions[first].pc // self.config.block_bytes):
                break
            end += 1
        memory.prefetch(instructions[first], instructions[end-1], cycle)
        self.targets.append((end, cycle + self.config.predictor_latency))
        self.predicted_position = end
        self.events['fdip_targets'] += 1

    def advance(self, cycle, instructions, blocked=False, memory=None):
        c = self.config
        if blocked:
            self.events['frontend_recovery_cycles'] += 1
            return
        if c.fdip:
            if memory is None or not hasattr(memory, 'prefetch'):
                raise ValueError('fdip requires a component instruction prefetch adapter')
            self.predict_target(cycle, instructions, memory)
        # Decode runs before fetch. Ready uops become visible to rename next cycle.
        if self.fetch and self.fetch[0][1] <= cycle and len(self.decoded) >= c.decode_entries:
            self.events["decode_output_full"] += 1
        if self.fetch and self.fetch[0][1] > cycle:
            self.events["decode_input_not_ready"] += 1
        decoded = hits = 0
        while self.fetch and len(self.decoded) < c.decode_entries:
            op, ready, hit, last, signature = self.fetch[0]
            if ready > cycle:
                break
            if hit:
                if hits >= c.uop_cache_width:
                    self.events["uop_cache_width_limited"] += 1
                    break
                hits += 1
            else:
                if decoded >= c.decode_width:
                    self.events["decode_width_limited"] += 1
                    break
                decoded += 1
            self.fetch.popleft()
            self.decoded.append((op, cycle + (c.uop_cache_latency if hit else c.decode_latency)))
            if last and c.uop_cache_entries:
                block = op.pc // c.block_bytes
                if block not in self.cache and len(self.cache) >= c.uop_cache_entries:
                    del self.cache[next(iter(self.cache))]
                self.cache[block] = signature
        if cycle < self.blocked_until:
            self.events['predictor_latency_cycles'] += 1
            return
        if self.position < len(instructions) and len(self.fetch) >= self.capacity:
            self.events["fetch_buffer_full"] += 1
        active = {op.pc // c.block_bytes for op, *_ in self.fetch}
        for _ in range(self.width):
            if self.position == len(instructions) or len(self.fetch) >= self.capacity:
                break
            if c.fdip and (not self.targets or self.targets[0][1] > cycle):
                self.events['fdip_target_not_ready'] += 1
                break
            op = instructions[self.position]
            block = op.pc // c.block_bytes
            if not c.fdip and block not in active and len(active) >= c.ftq_entries:
                self.events['ftq_full'] += 1
                break
            # Keys exclude dynamic addresses and branch outcomes.
            if block not in self.fills:
                end = self.position
                while end < len(instructions):
                    item = instructions[end]
                    if item.pc // c.block_bytes != block or (end > self.position and item.pc != instructions[end-1].pc + instructions[end-1].length):
                        break
                    end += 1
                    if item.kind in ('branch', 'jump'):
                        break
                signature = tuple((i.kind, i.sources, i.dest, i.pc, i.length)
                                  for i in instructions[self.position:end])
                self.fills[block] = (end, signature, self.cache.get(block) == signature)
                self.events['uop_cache_hits' if self.fills[block][2] else 'uop_cache_misses'] += 1
            end, signature, hit = self.fills[block]
            self.position += 1
            if c.fdip and self.position == self.targets[0][0]:
                self.targets.popleft()
            last = self.position == end
            cache_delay = memory.fetch(op, cycle) if memory is not None else 0
            self.fetch.append((op, cycle + c.fetch_latency + cache_delay, hit, last, signature))
            active.add(block)
            if last:
                del self.fills[block]
            if op.kind in ('branch', 'jump'):
                if not c.fdip:
                    self.blocked_until = cycle + c.predictor_latency
                break

    def ready(self, cycle):
        return bool(self.decoded and self.decoded[0][1] <= cycle)

    def pop(self):
        return self.decoded.popleft()[0]
