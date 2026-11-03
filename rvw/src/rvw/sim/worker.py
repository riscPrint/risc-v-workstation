"""Run cocotb in a disposable process group owned by the adapter."""
import json
import os
from pathlib import Path
import sys


def main():
    from cocotb_tools.runner import get_runner
    out = Path(sys.argv[1])
    request = json.loads((out / 'request.json').read_text())
    # Inherited filters and result paths must not narrow or redirect this run.
    for key in list(os.environ):
        if key.startswith(('COCOTB_', 'GPI_')) or key in {'SIM_CMD_PREFIX', 'SIM_CMD_SUFFIX', 'WAVES'}:
            os.environ.pop(key)
    runner = get_runner(request['backend'])
    build_args = ['--assert', '-j', '2'] if request['backend'] == 'verilator' else ['-g2012']
    runner.build(sources=request['sources'], hdl_toplevel=request['top'],
                 build_dir=out / 'build', build_args=build_args, timescale=('1ns', '1ps'))
    # The runner constructs PYTHONPATH from sys.path.
    sys.path[:0] = request['python_paths']
    runner.test(test_module=request['test_module'], hdl_toplevel=request['top'],
                seed=int(sys.argv[2]), test_dir=out, results_xml=str(out / 'cocotb.xml'),
                extra_env={'RVW_COCOTB_BINDINGS': json.dumps(request)})


if __name__ == '__main__':
    main()
