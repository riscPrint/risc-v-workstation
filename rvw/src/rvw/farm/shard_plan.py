"""Build local/Kubernetes shard plans from one C1 run-many manifest."""
import hashlib
import json
from pathlib import Path


def plan(manifest, adapter, root, image, claim, shards=1, jobs=1, identity=None, resources=None,
         timeout=600, persistent=False, python='python3'):
    if shards < 1 or jobs < 1 or not adapter or not isinstance(adapter, list):
        raise ValueError('positive shard/job counts and adapter argument array required')
    if persistent and jobs != 1:
        raise ValueError('persistent shards require jobs=1 and one configuration')
    rows = [json.loads(line) for line in Path(manifest).read_text().splitlines() if line.strip()]
    if not rows or any('config' not in r or 'seed' not in r for r in rows):
        raise ValueError('manifest must have explicit config and seed per cell')
    if persistent and (jobs != 1 or len({r['config'] for r in rows}) != 1):
        raise ValueError('persistent shards require jobs=1 and one configuration')
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
        shard = index % len(groups)
        local = len(groups[shard])
        relative = f'shards/{shard}/cells/{local}' if persistent else f'cells/{index}'
        destination = root / relative
        expected = {'elf_sha256': digest, 'config': row['config'], 'seed': row['seed']}
        for key in ('max_cycles', 'mem_latency'):
            if key in row:
                expected[key] = row[key]
        for key, value in (identity or {}).items():
            if key in expected and expected[key] != value:
                raise ValueError('identity claim differs from manifest: ' + key)
            expected[key] = value
        captured = dict(row, elf=str(elf), out=str(destination))
        if persistent:
            captured.setdefault('id', Path(row['elf']).name)
        groups[shard].append((captured, dict(path=relative + '/result.json', contract='C1', identity=expected)))
    planned = []
    for index, group in enumerate(groups):
        path = root / f'shard-{index}.jsonl'
        path.write_text(''.join(json.dumps(row) + '\n' for row, _ in group))
        results = [result for _, result in group]
        command = [*adapter, 'run-many', '--manifest', str(path), '--jobs', str(jobs)]
        if persistent:
            command = ['nice', '-n', '10', python, '-m', 'rvw.farm.native_shard', '--manifest', str(path),
                       '--adapter', json.dumps(adapter), '--out', str(root / 'shards' / str(index)),
                       '--timeout', str(timeout)]
            results.append(dict(path=f'shards/{index}/results.json', contract='C3',
                identity={'config': group[0][0]['config']}, tests=[dict(id=row['id'], seed=row['seed'],
                    elf_sha256=cell['identity']['elf_sha256'], run=f'cells/{i}')
                    for i, (row, cell) in enumerate(group)]))
        planned.append(dict(command=command, results=results))
    document = dict(name='rvw-' + hashlib.sha256(str(root).encode()).hexdigest()[:12], image=image,
                    timeout=timeout + 60 if persistent else timeout, shards=planned,
                    resources=resources or {'requests': {'cpu': str(jobs), 'memory': '1Gi'}},
                    volumes=[dict(claim=claim, mount=str(root))], expected_cells=len(rows), shared_root=str(root),
                    execution_mode='persistent' if persistent else 'process')
    (root / 'plan.json').write_text(json.dumps(document, indent=2))
    return document
