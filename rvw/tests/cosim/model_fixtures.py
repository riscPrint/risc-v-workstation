"""Captured model builders shared by the cosim tests."""
from argparse import Namespace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import weakref

from rvw.common.capture import Capture
from rvw.cosim import generate as generator, sail, sail_config, spike
from rvw.cosim.inputs import Inputs


def load_shim(path, source=None):
    temporary = TemporaryDirectory(prefix="rvw-test-shim-")
    try:
        inputs = spike.capture_shim(Capture(Path(temporary.name) / "inputs"), path, source)
        library = spike.load_shim(inputs)
        library._test_inputs = temporary
        return library
    except BaseException:
        temporary.cleanup()
        raise


def Spike(platform, elf, library=None):
    temporary = TemporaryDirectory(prefix="rvw-test-spike-")
    try:
        capture = Capture(Path(temporary.name) / "inputs")
        image = capture.file(elf)
        shim = spike.capture_shim(capture, library or os.environ.get("RVW_SPIKE_SHIM") or
                                 spike.SHIM_SOURCE.parent / "build/librvw_spike.so")
        model = spike.Spike(platform, image.copy, shim=shim)
        weakref.finalize(model, temporary.cleanup)
        return model
    except BaseException:
        temporary.cleanup()
        raise


def Sail(platform, elf, trace, executable, config=None, timeout=120, *, default_config=None):
    temporary = TemporaryDirectory(prefix="rvw-test-sail-")
    try:
        capture = Capture(Path(temporary.name) / "inputs")
        elf, trace = capture.file(elf).copy, capture.file(trace).copy
        config = capture.file(config).copy if config else None
        if config is None and default_config is None:
            default_config = sail_config.query(executable, ["--print-default-config",
                *(["--rv32"] if platform.xlen == 32 else [])], timeout)
        model = sail.Sail(platform, elf, trace, executable, config, timeout,
                          env=os.environ.copy(), default_config=default_config)
        weakref.finalize(model, temporary.cleanup)
        return model
    except BaseException:
        temporary.cleanup()
        raise


def generate(elf, out, platform, limit=1000000):
    with TemporaryDirectory(prefix="rvw-test-generate-") as directory:
        config = Path(directory) / "platform.json"
        # The test Platform describes exactly the selected model settings.
        settings = platform.describe()
        for key in ("ram", "mmio"):
            settings[key] = [{"base": base, "size": size} for base, size in getattr(platform, key)]
        config.write_text(json.dumps(settings))
        args = Namespace(cosim_action="generate", elf=elf, out=out, core=platform.name,
                         platform=config, max_instructions=limit)
        inputs = Inputs(args, directory)
        return generator.generate(inputs.args.elf, inputs.args.out, inputs.platform, limit,
                                  shim=inputs.shim, verify=inputs.capture.verify_tools,
                                  elf_source=inputs.identity("elf")["resolved"])
