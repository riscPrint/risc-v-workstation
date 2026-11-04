"""Optional GUI probes. Presence does not establish a working GUI session."""
import shutil
from rvw.common.proc import run_group

GUI = {
    'waves': ('surfer', ['--version'], ['wave_viewer']),
    'ide': ('code', ['--version'], ['vscode_extensions']),
}


def probe(feature):
    executable, args, capabilities = GUI[feature]
    path = shutil.which(executable)
    record = dict(feature=feature, executable=path, version=None, capabilities=capabilities,
                  qualification='version_probe_only', status='error')
    if path is None:
        record['reason'] = f'Install {executable} and add it to PATH.'
        return record
    try:
        done = run_group([path, *args], timeout=15, capture=True)
        record['version'] = (done.stdout or done.stderr or '').strip()
        record['status'] = 'ready' if done.returncode == 0 and record['version'] else 'error'
        record['reason'] = 'GUI session not tested.'
        if feature == 'ide' and record['status'] == 'ready':
            extensions = run_group([path, '--list-extensions', '--show-versions'], timeout=15, capture=True)
            installed = (extensions.stdout or '').splitlines()
            record['extensions'] = installed
            record['workstation_extension'] = next((x for x in installed if x.lower().startswith('riscprint.risc-v-workstation@')), None)
            if extensions.returncode != 0 or record['workstation_extension'] is None:
                record.update(status='error', reason='Install the RISC-V Workstation VS Code extension.')
    except OSError as exc:
        record['reason'] = str(exc)
    return record
