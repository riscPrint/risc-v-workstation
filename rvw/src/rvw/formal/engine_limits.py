"""Classify observed native failures without turning them into proof answers."""
from pathlib import Path
import re


def avy_failure(directory, text):
    if not re.search(r'returncode=-11\b', text):
        return {}
    models = list(Path(directory).glob('problem/model/design_aiger_fold.aig'))
    if len(models) != 1:
        return {'reason': 'avy_sigsegv'}
    header = models[0].read_bytes().split(b'\n', 1)[0].split()
    if len(header) < 6 or header[0] != b'aig':
        return {'reason': 'avy_sigsegv'}
    _, inputs, latches, outputs, gates = map(int, header[1:6])
    classes = []
    if latches == 0:
        classes.append('zero_latches')
    if outputs != 1:
        classes.append('multiple_outputs' if outputs > 1 else 'no_outputs')
    return {'reason': 'avy_sigsegv', 'observed_input_classes': classes,
            'aiger_shape': {'inputs': inputs, 'latches': latches, 'outputs': outputs, 'gates': gates},
            'unsupported_input': bool(classes)}


def rlive_failure(stdout, stderr):
    if "unexpected argument '--no-ic3-pred-prop'" in stdout + stderr:
        return {'reason': 'unsupported_backend_cli',
                'unsupported_input_class': 'native_rlive_with_internal_no_ic3_pred_prop',
                'detail': 'rIC3 rlive invokes an option removed from its own CLI; use l2s or k-live'}
    return {}
