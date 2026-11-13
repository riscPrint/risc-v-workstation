"""Trace-driven architectural comparison and reference trace generation over MCP."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler

S = {"type": "string"}
COMMON = {"project": {**S, "description": "project file or directory"}, "elf": {**S, "description": "RISC-V ELF matching the trace and platform"},
          "core": {**S, "description": "bundled platform name, or label with platform"},
          "platform": {**S, "description": "per-core platform JSON path"}}


def mcp_tools():
    from .doctor import mcp_tools as doctor_tools
    from .exchange_cli import mcp_tools as exchange_tools
    from .vector_source import mcp_tools as vector_tools
    from .adjudicate import mcp_tools as adjudication_tools
    from .qemu import mcp_tools as qemu_tools
    return [
        *doctor_tools(),
        *qemu_tools(),
        *adjudication_tools(),
        *exchange_tools(),
        *vector_tools(),
        ToolSpec("cosim_check", "Check a recorded C2 RVFI trace against Spike or Sail to locate the first architectural mismatch. "
                 "Preserves synchronization scope and matching-prefix/end status. A match does not mean the program "
                 "passed: check end_status. The Sail executable comes from RVW_SAIL on the server. "
                 "Large traces run as a cancellable job.",
                 schema({**COMMON, "trace": S, "model": {**S, "enum": ["spike", "sail"], "default": "spike"},
                         "history": {"type": "integer", "minimum": 0, "default": 10},
                         "strict": {"type": "boolean", "default": False,
                                    "description": "disable all synchronization"},
                         "strict_sync": {"type": "array", "items": {"enum": ["counter", "mmio", "csr", "irq"]},
                                         "description": "synchronization kinds to disable; the others stay on"},
                         "sail_config": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0, "default": 120}},
                        ["elf", "trace"]), handler("rvw.cosim.cli", "check"), long=True,
                 annotations={"readOnlyHint": True},
        side_effects='long-running; reads trace and ELF; launches selected Spike or Sail reference', native_tools=('Spike', 'Sail'),
        ),
        ToolSpec("cosim_generate", "Generate a C2 trace from Spike for an ELF, for reference fixtures or later comparison. "
                 "Writes out (refused if out is the ELF or an existing file that is not a C2 trace) and returns "
                 "reproduction metadata; runs as a cancellable job.",
                 schema({**COMMON, "out": S, "max_instructions": {"type": "integer", "minimum": 1, "default": 1000000}},
                        ["elf", "out"]), handler("rvw.cosim.cli", "generate"), long=True,
        side_effects='long-running; launches Spike; writes reference trace under out', native_tools=('Spike',),
        ),
    ]
