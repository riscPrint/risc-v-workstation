"""`--json` output: stdout gets exactly one strict JSON document, or nothing.

The document is serialized fully (no NaN or Infinity, which are not JSON) before one write, so a value
that JSON cannot encode never leaves half a document on stdout. Human messages go to stderr (`say`).
"""
from __future__ import annotations

import json
import sys


class JsonOutputError(ValueError):
    """The result cannot be written as JSON; nothing was written to stdout."""


def dumps(obj, **kw) -> str:
    try:
        return json.dumps(obj, allow_nan=False, **kw)
    except (TypeError, ValueError, RecursionError) as e:
        raise JsonOutputError(f"result is not JSON ({type(e).__name__}: {e}); nothing written") from e


def write(obj, **kw) -> None:
    """Serialize `obj` fully, then write it and a newline to stdout. Raises JsonOutputError first."""
    text = dumps(obj, **kw) + "\n"
    sys.stdout.write(text)
    sys.stdout.flush()


def say(prefix: str, msg: str) -> None:
    """A progress line, always on stderr, so stdout stays free for the result."""
    print(f"[{prefix}] {msg}", file=sys.stderr, flush=True)
