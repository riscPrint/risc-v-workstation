import os
from pathlib import Path
import subprocess
import pytest


@pytest.fixture(scope='session')
def spike_devices(tmp_path_factory):
    prefix = os.environ.get('RVW_DEVICE_SPIKE_PREFIX')
    if not prefix:
        pytest.skip('set RVW_DEVICE_SPIKE_PREFIX to build the native Spike device oracle')
    prefix = Path(prefix)
    out = tmp_path_factory.mktemp('spike-devices') / 'oracle'
    subprocess.run(['c++', '-std=c++17', '-I' + str(prefix / 'include'),
                    str(Path(__file__).with_name('spike_devices.cc')),
                    '-L' + str(prefix / 'lib'), '-Wl,-rpath,' + str(prefix / 'lib'),
                    '-lriscv', '-lfesvr', '-o', str(out)], check=True)

    def run(kind, actions):
        result = subprocess.run([str(out), kind], input='\n'.join(actions)+'\n',
                                text=True, capture_output=True, check=True, timeout=20)
        return [tuple(map(int, line.split())) for line in result.stdout.splitlines()]
    return run
