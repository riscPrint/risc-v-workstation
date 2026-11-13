"""Read owned C1 members without scanning captured input fixtures."""
from pathlib import Path
from rvw.results import load_run_set
from rvw.results.generation import has_store,open_current


def owned_run_paths(directory):
    root=Path(directory)
    if has_store(root):
        generation=open_current(root)
        if generation.entry('run.json') is not None:
            suites=load_run_set(generation)
        elif generation.entry('result.json') is not None:
            return [generation.path/'result.json']
        else:
            raise ValueError('result generation has no owned C1/C3 members')
    elif (root/'run.json').is_file():
        suites=load_run_set(root)
    elif (root/'result.json').is_file():
        return [root/'result.json']
    else:
        return sorted(root.rglob('result.json'))  # Legacy unowned adapter output.
    return [suite.path/test.run for suite in suites for test in suite.tests if test.run]


def run_paths_under(directory):
    """C1 members of every owned result below DIRECTORY, each once.

    A regression output holds each run twice (its sealed generation and the
    current view), so a plain rglob counts every C1 result two times. Stop at
    the first owned root on each branch and read only its members."""
    root=Path(directory)
    if not root.is_dir():
        return []
    if has_store(root) or (root/'run.json').is_file() or (root/'result.json').is_file():
        return owned_run_paths(root)
    paths=[]
    for child in sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()):
        paths.extend(run_paths_under(child))
    return paths
