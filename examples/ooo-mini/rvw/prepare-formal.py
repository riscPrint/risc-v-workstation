#!/usr/bin/env python3
"""Prepare selected native checks at small bounds; preserve activation jobs."""
import importlib.util
import os
from pathlib import Path

home = Path(os.environ['RVW_HOME'])
root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prepare_connected', home / 'SpinalChecks/scripts/prepare-connected-formal.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.prepare(root / 'out/rtl', root / 'out/rtl/Core.checks.json', root / 'out/formal-jobs',
               ['ooo.property:rob_bound', 'ooo.property:zero_map', 'queue.occupancy:rob',
                'ooo.property:issue_operands', 'freelist.conservation:rename'], depth=8)
