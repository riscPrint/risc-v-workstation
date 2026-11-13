"""A native C1 adapter does not need a --version command."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe

pytestmark = pytest.mark.fast


def test_native_adapter_without_version_runs(fake, tmp_path):
    compiler = shutil.which('cc')
    if compiler is None:
        pytest.skip('C compiler needed for native adapter fixture')
    script = Path(__file__).with_name('fake_adapter.py')
    source = tmp_path / 'adapter.c'
    source.write_text('''#include <string.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "--version")) return 2;
    char *args[argc + 2];
    args[0] = PYTHON; args[1] = SCRIPT;
    for (int i = 1; i < argc; i++) args[i + 1] = argv[i];
    args[argc + 1] = 0;
    execv(args[0], args);
    return 127;
}
'''.replace('PYTHON', json.dumps(sys.executable)).replace('SCRIPT', json.dumps(str(script))))
    executable = tmp_path / 'native-adapter'
    subprocess.run([compiler, str(source), '-o', str(executable)], check=True, timeout=30,
                   capture_output=True)
    core = load_config(str(fake.config))
    core.adapter = [str(executable)]
    core.cache_paths.append(script)
    runner = Runner(core, describe(fake.repo), tmp_path / 'out',
                    RunOptions(index=False, use_cache=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['ok'], (runner.input_change, summary)
    assert len(fake.calls('run')) == 3
