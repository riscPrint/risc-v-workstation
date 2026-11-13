#!/usr/bin/env python3
"""Regenerate the finite temporal support table from its semantic test corpus."""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
corpus = ast.parse((root / 'rvw/tests/formal/test_temporal_composition.py').read_text())
cases = ast.literal_eval(next(node.value for node in corpus.body
                             if isinstance(node, ast.Assign)
                             and any(isinstance(t, ast.Name) and t.id == 'CASES'
                                     for t in node.targets)))
local_corpus = ast.parse((root / 'rvw/tests/formal/test_local_capture.py').read_text())
local_features = ast.literal_eval(next(node.value for node in local_corpus.body
                                     if isinstance(node, ast.Assign)
                                     and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES'
                                             for t in node.targets)))
cases += [(feature,) for feature in local_features]
rows = ['| Construct | Corpus | Scope |', '|---|---|---|']
rows += [f'| `{feature}` | positive and negative native case | finite, single clock |'
         for feature, *_ in cases]
(root / 'rvw/src/rvw/formal/TEMPORAL_SUPPORT.md').write_text('\n'.join(rows) + '\n')
