"""Functions behind the fault CLI and MCP tools."""
import json
import shlex
from pathlib import Path

from . import campaign


def run(plan, adapter, elf, out, jobs=1, max_cycles=None, timeout=600, detections=None, watchdog=False):
    plan_data = json.loads(Path(plan).read_text())
    if plan_data.get('schema') != campaign.PLAN_SCHEMA:
        raise ValueError(f'plan schema must be {campaign.PLAN_SCHEMA}')
    rules = json.loads(Path(detections).read_text()) if detections else None
    command = shlex.split(adapter) if isinstance(adapter, str) else list(adapter)
    summary, _ = campaign.run_campaign(plan_data, command, elf, out, jobs=jobs, max_cycles=max_cycles,
                                       timeout=timeout, detections=rules, watchdog=watchdog)
    (Path(out) / 'plan.json').write_text(json.dumps(plan_data, indent=2) + '\n')
    return summary


def report(directory):
    directory = Path(directory)
    plan_data = json.loads((directory / 'plan.json').read_text())
    outcomes = json.loads((directory / 'outcomes.json').read_text())
    return campaign.report(plan_data, outcomes)


def sites(db, include=None, exclude=None, generated=False):
    found = campaign.sites(db, include=include or ['*'], exclude=exclude or [], generated=generated)
    return {'sites': found, 'bits': sum(s['width'] for s in found)}
