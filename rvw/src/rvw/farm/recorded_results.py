"""Read farm C3 history without descending into C5 bundle generations."""
import json
from pathlib import Path
from rvw.results import find_results
from rvw.results.generation import has_store


def recorded_results(root):
    root = Path(root)
    summary = root/'summary.json'
    if summary.is_file():
        # A bundle owns its captured inputs and generations, not regression suites.
        data = json.loads(summary.read_text())
        if data.get('schema') == 'rvw.bundle/1' and not any(
                (root/name).exists() for name in ('run.json', 'results.json')):
            return []
    if has_store(root) or any((root/name).exists() for name in (
            'run.json', 'results.json', '.rvw-private-inputs', '.rvw-cache-entry')):
        return find_results(root)
    found = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.is_symlink():
            found.extend(recorded_results(child))
    return found
