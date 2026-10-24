"""Use the command capture path for path-based perf test inputs."""
from rvw.perf.cli import execute_json


def analyze(path, **options):
    return execute_json([str(path)], **options)
