"""Conservative capabilities for the supported native invocation profiles.

These are adapter guarantees, not a complete description of each simulator.
A feature absent from a profile must not be silently approximated.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Backend:
    values: str
    scheduling: str
    x_handling: str
    languages: tuple[str, ...]
    assertions: str
    foreign: tuple[str, ...]
    coverage: str
    features: tuple[str, ...]

    def to_dict(self):
        return asdict(self)


BACKENDS = {
    "verilator": Backend(
        "2-state", "compiled; cocotb edge and timer callbacks",
        "X/Z collapse; no unknown propagation guarantee",
        ("Verilog", "synthesizable SystemVerilog subset"),
        "immediate assertions enabled; concurrent SVA not guaranteed",
        ("VPI", "DPI-C"), "not enabled by this adapter",
        ("two_state", "timer", "clock", "immediate_assertions", "vpi")),
    "icarus": Backend(
        "4-state", "event-driven; cocotb edge, timer and ReadOnly callbacks",
        "preserves X/Z values; no pessimistic X-propagation guarantee",
        ("Verilog", "SystemVerilog subset (-g2012)"),
        "immediate assertions; concurrent SVA not guaranteed",
        ("VPI",), "not enabled by this adapter",
        ("four_state", "xz_values", "timer", "clock", "read_only", "immediate_assertions", "vpi")),
}


def require(backend: str, features=()) -> Backend:
    if not isinstance(backend, str) or backend not in BACKENDS:
        raise ValueError(f"unsupported backend: {backend}; supported: {', '.join(BACKENDS)}")
    profile = BACKENDS[backend]
    missing = sorted(set(features) - set(profile.features))
    if missing:
        raise ValueError(f"{backend} cannot provide required features: {', '.join(missing)}")
    return profile
