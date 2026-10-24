#!/usr/bin/env python3
"""Record source revisions once. Generated RTL supplies the design content identity."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'rvw/src'))
from rvw.regress.source import describe

core, tools = map(Path, sys.argv[1:])
source = (json.loads(os.environ['RVW_CAPTURE_SOURCE']) if os.environ.get('RVW_CAPTURE_SOURCE')
          else describe(core).to_dict())
harness = describe(tools)
source.update(tools_repo=str(tools), tools_rev=harness.rev, tools_dirty=harness.dirty)
print(json.dumps(source, sort_keys=True))
