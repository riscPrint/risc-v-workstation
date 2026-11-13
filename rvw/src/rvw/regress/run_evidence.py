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
