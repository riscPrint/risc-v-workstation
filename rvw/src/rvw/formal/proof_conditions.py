"""Retain the exact elaborated environment predicate and source context."""
from hashlib import sha256
from pathlib import Path
import re


def condition(module, name, cell, directory):
    src = cell.get('attributes', {}).get('src', '')
    row = {'module': module, 'cell': name, 'source': src,
           'predicate_bits': cell.get('connections', {}).get('A', []),
           'enable_bits': cell.get('connections', {}).get('EN', [])}
    # Source spans can start at the preceding statement's terminator.
    match = re.fullmatch(r'([^|:]+):(\d+)\.\d+-(\d+)\.\d+', src)
    if match:
        path = Path(directory) / match[1]
        if path.is_file():
            data = path.read_bytes()
            lines = data.decode(errors='replace').splitlines()
            row.update(source_sha256=sha256(data).hexdigest(),
                       source_excerpt='\n'.join(lines[int(match[2])-1:int(match[3])]))
    return row
