"""Known-failures files (TOML): failures accepted for now, each with a reason and the revision it was
recorded at. A test matches only with the same suite, id and signature (and config, when given), so
a different failure of the same test is still new.

    [[known]]
    suite = "riscv-tests"
    id = "rv64mi-p-instret_overflow"
    signature = "fail:3"          # may use * and ? wildcards
    config = "small"              # optional; absent = any config
    reason = "BOOM counts the minstret write at commit (upstream behaviour)"
    recorded_at_rev = "0cb0b69"
    recorded_at = "2026-10-20T21:03:11Z"
"""
from __future__ import annotations

import tempfile
from rvw.common.capture import Capture
import fnmatch
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

FIELDS = ("suite", "id", "signature", "config", "reason", "recorded_at_rev", "recorded_at")


def _validate(entry: dict) -> None:
    unknown = entry.keys() - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    for name in FIELDS:
        if name not in entry and name not in ("suite", "id", "signature"):
            continue
        value = entry.get(name)
        if value is None and name in ("config", "recorded_at"):
            continue
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        if name in ("suite", "id", "signature", "config") and not value.strip():
            raise ValueError(f"{name} must be a non-empty string")


def _line(text: str, index: int | None = None, field: str | None = None) -> int:
    """Locate ordinary TOML keys for diagnostics; TOML parsing remains tomllib's job."""
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if re.match(
        r'''\s*\[\[\s*(?:known|"known"|'known')\s*\]\]''', line)]
    start = headers[index] if index is not None and index < len(headers) else 0
    end = headers[index + 1] if index is not None and index + 1 < len(headers) else len(lines)
    if field:
        key = re.escape(field)
        for i in range(start, end):
            if re.match(rf'''\s*(?:{key}|"{key}"|'{key}')\s*=''', lines[i]):
                return i + 1
    return start + 1


@dataclass
class Known:
    suite: str
    id: str
    signature: str
    reason: str = ""
    recorded_at_rev: str = ""
    config: str | None = None
    recorded_at: str | None = None

    def __post_init__(self):
        _validate({k: getattr(self, k) for k in FIELDS})

    def matches(self, suite: str, tid: str, signature: str | None, config: str | None = None) -> bool:
        if self.suite != suite or self.id != tid or signature is None:
            return False
        if self.config is not None and self.config != config:
            return False
        if any(c in self.signature for c in "*?["):
            return fnmatch.fnmatchcase(signature, self.signature)
        return self.signature == signature

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in FIELDS if getattr(self, k) not in (None, "")}
        return d


class KnownInputs(list):
    capture: dict | None = None


def load_known(path: Path | None) -> list[Known]:
    if path is None or not Path(path).is_file():
        out = KnownInputs()
        out.capture = {"source": str(path) if path else None, "present": False}
        return out
    with tempfile.TemporaryDirectory(prefix="rvw-known-") as directory:
        capture = Capture(Path(directory) / "capture")
        item = capture.file(path)
        text = item.copy.read_text()
        raw = tomllib.loads(text)
        record = capture.record()
    out = KnownInputs()
    out.capture = record
    unknown = raw.keys() - {"known"}
    if unknown:
        key = sorted(unknown)[0]
        raise ValueError(f"{path}:{_line(text, field=key)}: unknown known-failures field {key}")
    entries = raw.get("known", [])
    if not isinstance(entries, list):
        raise ValueError(f"{path}:{_line(text, field='known')}: known must be an array of tables")
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise ValueError(f"{path}:{_line(text, i)}: known[{i}] must be a table")
        try:
            _validate(e)
        except ValueError as exc:
            unknown = e.keys() - set(FIELDS)
            field = sorted(unknown)[0] if unknown else str(exc).split()[0]
            raise ValueError(f"{path}:{_line(text, i, field)}: known[{i}]: {exc}") from exc
        out.append(Known(**e))
    return out


def _toml_str(s: str) -> str:
    out = ['"']
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return _toml_str(str(v))


HEADER = ("# Known failures for `rvw regress compare` / `gate`. A failure listed here does not reject a\n"
          "# change; a different signature of the same test still does. Edit by hand or with\n"
          "# `rvw regress known add`.\n")


def save_known(path: Path, entries: list[Known]) -> None:
    lines = [HEADER]
    for e in sorted(entries, key=lambda e: (e.suite, e.id, e.config or "", e.signature)):
        lines.append("[[known]]")
        for k, v in e.to_dict().items():
            lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines))
    tmp.replace(path)


def add_known(path: Path, new: list[Known]) -> tuple[int, int]:
    """Add entries, replacing any with the same (suite, id, config, signature). Returns (added, replaced)."""
    entries = load_known(path)
    added = replaced = 0
    for n in new:
        k = (n.suite, n.id, n.config, n.signature)
        before = len(entries)
        entries = [e for e in entries if (e.suite, e.id, e.config, e.signature) != k]
        replaced += before - len(entries)
        added += before == len(entries)
        entries.append(n)
    save_known(path, entries)
    return added, replaced


def remove_known(path: Path, suite: str, tid: str, signature: str | None = None) -> int:
    entries = load_known(path)
    keep = [e for e in entries if not (e.suite == suite and e.id == tid and (signature is None or e.signature == signature))]
    save_known(path, keep)
    return len(entries) - len(keep)
