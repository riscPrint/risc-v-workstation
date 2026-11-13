"""Read first differences only from comparisons bound to the recorded C1 bytes."""
import hashlib
import json
from pathlib import Path
from rvw.results import load_run


def observed_mismatch(directory, test, core, config):
    directory = Path(directory)
    path = directory/'cosim.json'
    if not path.is_file():
        return None
    comparison = json.loads(path.read_text())
    if comparison.get('schema') != 'rvw.cosim/1' or comparison.get('status') != 'mismatch':
        return None
    run = load_run(directory)
    if (run.core, run.config, run.seed, run.status, run.elf_sha256) != (
            core, config, test.seed, test.status, test.extra.get('elf_sha256')):
        raise ValueError('comparison C1 does not match its C3 entry')
    trace = run.artifact('rvfi_trace')
    if trace is None:
        raise ValueError('comparison has no C1 trace')
    digests = {f.get('sha256') for f in comparison.get('reproduction', {}).get('capture', {}).get('files', [])}
    if not run.elf_sha256 or not {run.elf_sha256, hashlib.sha256(trace.read_bytes()).hexdigest()} <= digests:
        raise ValueError('comparison does not capture the C1 ELF and trace hashes')
    mismatch = comparison.get('mismatch', {})
    actual = mismatch.get('actual', {})
    pc, instruction = mismatch.get('pc'), actual.get('insn')
    if pc is None or instruction is None:
        raise ValueError('comparison lacks first-mismatch PC or instruction')
    return dict(pc=pc, instruction=instruction, comparison_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                model=comparison.get('model'), synchronized=comparison.get('synchronized'),
                applied_masks=comparison.get('applied_masks', []),
                recent_synchronizations=comparison.get('recent_synchronizations', []))
