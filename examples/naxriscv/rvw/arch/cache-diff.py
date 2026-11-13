#!/usr/bin/env python3
"""Compare cache identity receipts without exposing the full inherited environment."""
import json
from pathlib import Path
import sys


def compare(old, new):
    before, after = old["tools"]["native_build"], new["tools"]["native_build"]
    keys = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    return dict(old_sha256=before["sha256"], new_sha256=after["sha256"],
                old_namespace=before["namespace"], new_namespace=after["namespace"],
                changed_fields=keys,
                changed_environment_fields=sorted(k for k in before["environment"].keys() | after["environment"].keys()
                                                 if before["environment"].get(k) != after["environment"].get(k)),
                resolved_tools_equal=before["tools"] == after["tools"],
                emitted_rtl_equal=old["rtl_sha256"] == new["rtl_sha256"],
                limits=["environment_sha256 cannot reveal other inherited variable changes",
                        "PATH remains part of identity because descendant tool lookup is not fully pinned"])


if __name__ == "__main__":
    print(json.dumps(compare(*(json.loads(Path(p).read_text()) for p in sys.argv[1:])), indent=2))
