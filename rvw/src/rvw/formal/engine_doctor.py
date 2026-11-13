"""Dependency diagnostics. Presence does not qualify a native engine."""
import shutil
from .portfolio import ENGINES, installed


def diagnose():
    rows = installed()
    for name, row in rows.items():
        backend, deps, modes = ENGINES[name]
        features = ['bounded_search' if m == 'bmc' else 'unbounded_safety' for m in modes]
        if name.startswith('smtbmc:') and 'prove' in modes:
            features.append('uninterpreted_datapath')
        if name == 'aiger:rIC3':
            features.extend(['aiger_liveness_to_safety', 'aiger_k_liveness', 'experimental_aiger_rlive'])
        row.update(backend=backend, features=features,
                   enabled_features=features if row['status'] == 'installed' else [],
                   executables={d: shutil.which(d) for d in deps},
                   qualification='not_measured')
    return {'schema': 'rvw.formal-doctor/1', 'status': 'pass', 'engines': rows,
            'limits': 'Diagnostic completed. Installed means dependencies were found on PATH. '
                      'Run engine-bench for native qualification. No proof was run.'}
