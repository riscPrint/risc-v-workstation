#!/usr/bin/env python3
"""Read an existing native capture for the pinned litmus outcome checker."""
import json
import os
from pathlib import Path
import sys
from litmus_programs import parse
from litmus_capture import capture


def outcome(test):
    _, _, projection, digest = parse(test)
    base = Path(os.environ.get('RVW_SMP_LITMUS_OUT', Path(__file__).parent/'out/litmus'))
    root = base/(os.environ.get('RVW_SMP_LITMUS_PREFIX', '')+Path(test).stem)
    return capture(root, projection, digest)


if __name__ == '__main__':
    print(json.dumps(outcome(sys.argv[1])))
