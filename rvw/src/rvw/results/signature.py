"""Failure signatures: a short, stable fingerprint of how a test failed.

Scala locations identify assertions across generated-HDL line changes. Without a Scala location,
keep the HDL file and line. Without either location, bind the full message. A signature
is `<status>` or `<status>:<detail>`:

    fail:3                    tohost fail code 3
    timeout                   max cycles reached (a property of the core and the program)
    timeout:wall-clock        the wall clock ran out (machine load or a hung process; inconclusive)
    assert:lsu.scala:1241     HDL assertion, located by its Scala source line
    assert:core.sv:4          HDL assertion without a Scala location
    assert:sha256:<digest>    assertion without a location, hash of the full message
    assert:<Type>@Foo.scala:12   testbench exception: its class and the first Scala location
    rvfi_error:105            riscv-formal monitor error, by its error code
    rvfi_error:sha256:<digest>  monitor error without a code, full message hash
    error:<message>           harness error
"""
from __future__ import annotations

import hashlib
import re

MAX_LEN = 120

_SCALA_LOC = re.compile(r"([A-Za-z_][\w$-]*\.scala):L?(\d+)")
_HDL_LOC = re.compile(r"([A-Za-z_][\w$.-]*\.(?:sv|v|vhdl|vhd)):(\d+)(?::\d+)?")
_ABS_PATH = re.compile(r"(?:[A-Za-z]:)?(?:/[^\s/:'\"()]+)+/([^\s/:'\"()]+)")
_HDL_LINE = re.compile(r"(\.s?v|\.vhdl?|\.cpp|\.h):\d+(?::\d+)?")
_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_COUNTED = re.compile(r"\b(cycles?|time|seed|t|at|after|pc)(\s*[=:]?\s*)\d+\b", re.IGNORECASE)
_BIG_NUM = re.compile(r"(?<![\w.])\d{4,}(?![\w])")
_PREFIX = re.compile(r"^(%?(error|warning|fatal)\s*[:!-]\s*)+", re.IGNORECASE)
_SPACE = re.compile(r"\s+")
# "java.lang.IllegalStateException: ..." / "IllegalStateException: ..." at the start of a message
_EXCEPTION = re.compile(r"^\s*((?:[a-z_][\w]*\.)*)([A-Z][\w$]*(?:Exception|Error|Throwable|Failure))(?::\s*|\s*$)")
_BARE = {"Exception", "Error", "Throwable", "Failure"}
_RVFI_CODE = re.compile(r"monitor error\s+(\d+)", re.IGNORECASE)

WALL_CLOCK = "timeout:wall-clock"


def normalize_message(message: str | None) -> str:
    """Normalize a failure message into something stable across seeds, paths and revisions."""
    if not message:
        return ""
    lines = [l.strip() for l in message.splitlines() if l.strip()]
    if not lines:
        return ""
    m = lines[0]
    m = _PREFIX.sub("", m)
    m = _ABS_PATH.sub(r"\1", m)
    m = _HDL_LINE.sub(r"\1", m)
    m = _HEX.sub("0x*", m)
    m = _COUNTED.sub(lambda x: f"{x.group(1)}{x.group(2)}N", m)
    m = _BIG_NUM.sub("N", m)
    m = _SPACE.sub(" ", m).strip()
    return m[:MAX_LEN]


def scala_location(message: str | None) -> str | None:
    """First `File.scala:LINE` in a message, without any directory."""
    if not message:
        return None
    m = _SCALA_LOC.search(message)
    return f"{m.group(1)}:{m.group(2)}" if m else None


def exception_type(message: str | None) -> tuple[str, str] | None:
    """(simple class name, rest of the message) when the message starts with an exception class."""
    m = _EXCEPTION.match(message or "")
    if not m or (not m.group(1) and m.group(2) in _BARE):
        return None
    return m.group(2), message[m.end():]


def located_assertion(signature: str | None) -> bool:
    """Whether a saved assertion signature contains a complete source location."""
    if not signature or not signature.startswith("assert:"):
        return False
    detail = signature.removeprefix("assert:").split("@", 1)[-1]
    return bool(_SCALA_LOC.fullmatch(detail) or _HDL_LOC.fullmatch(detail))


def failure_signature(status: str, fail_code: int | None = None, message: str | None = None,
                      wall_clock: bool = False, rvfi_code: int | None = None) -> str | None:
    """Signature for a C1 status; None for a pass. `wall_clock`: the timeout was the wall clock's,
    not the cycle limit's. `rvfi_code`: the riscv-formal monitor's error code, if known."""
    if status == "pass":
        return None
    if status == "fail":
        return f"fail:{fail_code}" if fail_code is not None else "fail"
    if status == "timeout":
        return WALL_CLOCK if wall_clock else "timeout"
    if status == "rvfi_error":
        if rvfi_code is None:
            m = _RVFI_CODE.search(message or "")
            rvfi_code = int(m.group(1)) if m else None
        if rvfi_code is not None:
            return f"rvfi_error:{rvfi_code}"
        return "rvfi_error:sha256:" + hashlib.sha256((message or "").encode()).hexdigest()
    if status == "assert":
        exc = exception_type(message)
        loc = scala_location(message)
        if not loc:
            hdl = _HDL_LOC.search(message or "")
            if hdl:
                loc = f"{hdl.group(1)}:{hdl.group(2)}"
        if loc:
            return f"assert:{exc[0]}@{loc}" if exc else f"assert:{loc}"
        return "assert:sha256:" + hashlib.sha256((message or "").encode()).hexdigest()
    detail = normalize_message(message)
    return f"{status}:{detail}"[:MAX_LEN] if detail else status


def run_signature(run) -> str | None:
    """Signature of a `RunResult` (or a dict with the same keys)."""
    if isinstance(run, dict):
        get = run.get
        extra = run
    else:
        get = lambda k, d=None: getattr(run, k, d)  # noqa: E731
        extra = getattr(run, "extra", {}) or {}
    details = extra.get("details") if isinstance(extra.get("details"), dict) else {}
    code = details.get("rvfi_errcode")
    return failure_signature(get("status"), get("fail_code"), get("message"),
                             wall_clock=bool(extra.get("wall_clock_timeout")),
                             rvfi_code=code if isinstance(code, int) and not isinstance(code, bool) else None)
