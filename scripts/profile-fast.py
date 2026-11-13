#!/usr/bin/env python3
"""Profile the fast unit set. Write the report outside the repository.

rvw/.venv/bin/python scripts/profile-fast.py "$RUN_ROOT/fast.json" [--collect-only]
CPU fields exclude time spent waiting. Child CPU includes reaped subprocesses.
Fixture measurements overlap test measurements. Do not add both sets together.
"""
import json
import os
from pathlib import Path
import resource
import sys
import subprocess
import time

START = time.process_time()
import pytest


def sample():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time(), usage.ru_utime + usage.ru_stime


def elapsed(start):
    current = sample()
    return dict(cpu_s=current[0] - start[0], child_cpu_s=current[1] - start[1],
                load=os.getloadavg())


class Profile:
    def __init__(self, output):
        self.output = output
        self.revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        self.start = (START, 0)
        self.rows = []
        self.collection = None

    def pytest_collection_finish(self, session):
        self.collection = elapsed(self.start)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        start = sample()
        yield
        self.rows.append(dict(test=item.nodeid, **elapsed(start)))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        start = sample()
        yield
        self.rows.append(dict(fixture=fixturedef.argname, owner=fixturedef.baseid,
                              scope=fixturedef.scope, **elapsed(start)))

    def pytest_sessionfinish(self, session, exitstatus):
        self.output.write_text(json.dumps(dict(revision=self.revision, process_cpu_s=time.process_time(), total=elapsed(self.start), collection=self.collection,
                                              exit_code=int(exitstatus), rows=self.rows), indent=1))


if __name__ == '__main__':
    output = Path(sys.argv[1])
    raise SystemExit(pytest.main(['rvw/tests', '-m', 'fast', '--strict-markers', '-q',
                                 *sys.argv[2:]], plugins=[Profile(output)]))
