"""Build local/Kubernetes shard plans from one C1 run-many manifest."""
import hashlib
import json
from pathlib import Path


def plan(manifest, adapter, root, image, claim, shards=1, jobs=1, identity=None, resources=None, timeout=600):
    if shards < 1 or jobs < 1 or not adapter or not isinstance(adapter, list):
        raise ValueError('positive shard/job counts and adapter argument array required')
    rows = [json.loads(line) for line in Path(manifest).read_text().splitlines() if line.strip()]
    if not rows or any('config' not in r or 'seed' not in r for r in rows):
        raise ValueError('manifest must have explicit config and seed per cell')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / 'inputs'
    inputs.mkdir()
    groups = [[] for _ in range(min(shards, len(rows)))]
    for index, row in enumerate(rows):
        data = Path(row['elf']).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        elf = inputs / (digest + '.elf')
        if not elf.exists():
            elf.write_bytes(data)
        destination = root / 'cells' / str(index)
        expected = {'elf_sha256': digest, 'config': row['config'], 'seed': row['seed']}
        for key in ('max_cycles', 'mem_latency'):
            if key in row:
                expected[key] = row[key]
        for key, value in (identity or {}).items():
            if key in expected and expected[key] != value:
                raise ValueError('identity claim differs from manifest: ' + key)
            expected[key] = value
        groups[index % len(groups)].append((dict(row, elf=str(elf), out=str(destination)),
            dict(path=f'cells/{index}/result.json', contract='C1', identity=expected)))
    planned = []
    for index, group in enumerate(groups):
        path = root / f'shard-{index}.jsonl'
        path.write_text(''.join(json.dumps(row) + '\n' for row, _ in group))
        planned.append(dict(command=[*adapter, 'run-many', '--manifest', str(path), '--jobs', str(jobs)],
                            results=[result for _, result in group]))
    document = dict(name='rvw-' + hashlib.sha256(str(root).encode()).hexdigest()[:12], image=image,
                    timeout=timeout, shards=planned, resources=resources or {'requests': {'cpu': str(jobs), 'memory': '1Gi'}},
                    volumes=[dict(claim=claim, mount=str(root))], expected_cells=len(rows), shared_root=str(root))
    (root / 'plan.json').write_text(json.dumps(document, indent=2))
    return document
