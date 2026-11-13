#!/usr/bin/env python3
"""Regenerate temporal support from its semantic test corpora."""
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
unbounded = ast.parse((root / 'rvw/tests/formal/test_unbounded_semantics.py').read_text())
features = ast.literal_eval(next(node.value for node in unbounded.body
                                if isinstance(node, ast.Assign)
                                and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES'
                                        for t in node.targets)))
rows += [f'| `{feature}` | positive and negative native case | infinite trace, single clock; `formal liveness` |'
         for feature in features]
cross = ast.parse((root / 'rvw/tests/formal/test_cross_clock.py').read_text())
features = ast.literal_eval(next(node.value for node in cross.body
                                if isinstance(node, ast.Assign)
                                and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES'
                                        for t in node.targets)))
rows += [f'| `{feature.replace("|", "&#124;")}` | positive and negative native case | finite native timed replay; two clocks |'
         for feature in features]
sampled_live = ast.parse((root / 'rvw/tests/formal/test_live_sampled_native.py').read_text())
functions = ast.literal_eval(next(node.value for node in sampled_live.body
                                 if isinstance(node, ast.Assign)
                                 and any(isinstance(t, ast.Name) and t.id == 'FUNCTIONS'
                                         for t in node.targets)))
rows += [f'| `liveness ${function}` | positive and negative native case | single-clock liveness; sampled history |'
         for function in functions]
ranges = ast.parse((root / 'rvw/tests/formal/test_repetition_ranges.py').read_text())
features = ast.literal_eval(next(node.value for node in ranges.body
                                if isinstance(node, ast.Assign)
                                and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES'
                                        for t in node.targets)))
rows += [f'| `{feature}` | positive and negative native case | infinite trace, single clock; literal ranges |'
         for feature in features]
throughout = ast.parse((root / 'rvw/tests/formal/test_unbounded_throughout.py').read_text())
features = ast.literal_eval(next(node.value for node in throughout.body
                                if isinstance(node, ast.Assign)
                                and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES'
                                        for t in node.targets)))
rows += [f'| `{feature}` | positive and negative native case | infinite trace, single clock; Boolean guard |'
         for feature in features]
(root / 'rvw/src/rvw/formal/TEMPORAL_SUPPORT.md').write_text('\n'.join(rows) + '\n')
