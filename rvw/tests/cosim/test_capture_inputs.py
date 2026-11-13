"""C8 races at the comparison, Sail execution and publication read boundaries."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from race_injection import race_injector
from rvw.cosim import cli, sail as sail_module
from model_fixtures import generate
from rvw.cosim.spike import SHIM_SOURCE
from test_review16_sail import mul_elf


def digest(data):
    return hashlib.sha256(data).hexdigest()


def arguments(elf, trace, **options):
    from argparse import Namespace
    return Namespace(cosim_action="check", elf=elf, trace=trace, platform=None, core="boom",
                     model=options.get("model", "spike"), sail=options.get("sail", "unused"),
                     sail_config=options.get("sail_config"), timeout=30, history=3,
                     strict=False, strict_sync=())


@pytest.fixture
def command_inputs(tmp_path, elf, platform, monkeypatch):
    """Keep all mutable race targets local to this test."""
    image = tmp_path / "program.elf"
    image.write_bytes(elf.read_bytes())
    trace = tmp_path / "trace.jsonl"
    generate(image, trace, platform, 100)
    platform_path = tmp_path / "platform.json"
    original = Path(cli.__file__).parent / "configs/boom.json"
    platform_path.write_bytes(original.read_bytes())
    run = tmp_path / "result.json"
    run.write_text(json.dumps({"config": "original", "seed": 19}))
    root = SHIM_SOURCE.parent
    shim = tmp_path / "librvw_spike.so"
    shim.write_bytes((root / "build/librvw_spike.so").read_bytes())
    manifest = Path(str(shim) + ".manifest.json")
    built = json.loads((root / "build/librvw_spike.so.manifest.json").read_text())
    dependency = tmp_path / "libriscv.so"
    dependency.write_bytes(Path(built["spike_library"]).read_bytes())
    built["spike_library"] = str(dependency)
    manifest.write_text(json.dumps(built))
    source = tmp_path / "spike_shim.cc"
    source.write_bytes(SHIM_SOURCE.read_bytes())
    monkeypatch.setattr("rvw.cosim.spike.SHIM_SOURCE", source)
    monkeypatch.setenv("RVW_SPIKE_SHIM", str(shim))
    args = arguments(image, trace)
    args.platform = platform_path
    return args, dict(elf=image, trace=trace, platform=platform_path, core_run=run,
                      library=shim, manifest=manifest, dependency=dependency, source=source)


@pytest.mark.parametrize("name", ["elf", "trace", "platform", "core_run", "library", "manifest", "dependency", "source"])
@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_command_uses_one_capture_at_comparison(command_inputs, race_injector, name, replace, revert):
    args, paths = command_inputs
    target = paths[name]
    original = target.read_bytes()
    # Before: this boundary could alter consumed trace bytes, or the identities reported later.
    hook = race_injector.file(cli, "check", target, b"replaced input\n", when="before",
                              replace=replace, revert=revert)
    result, code = cli.calculate(args)
    assert hook.fired
    assert code == 0 and result["status"] == "match", result
    capture = result["reproduction"]["capture"]
    row = next(row for row in capture["files"] if row["source"] == str(target))
    assert row["sha256"] == digest(original)
    assert result["reproduction"]["core_run"]["seed"] == 19
    if name in ("elf", "trace", "platform"):
        assert result["reproduction"][name + "_sha256"] == digest(original)


@pytest.fixture
def sail_inputs(tmp_path, mul_elf, platform, sail):
    from rvw.cosim.platform import Platform
    path = tmp_path / "platform.json"
    data = json.loads((Path(cli.__file__).parent / "configs/boom.json").read_text())
    data.update(isa="rv64im_zicsr_zifencei", reference_isa=None, sail_overrides={}, csr_masks={},
                aligned_mem=False, mode_after_change=False, illegal_insn_tval="insn")
    path.write_text(json.dumps(data))
    image = tmp_path / "program.elf"
    image.write_bytes(mul_elf.read_bytes())
    trace = tmp_path / "trace.jsonl"
    generate(image, trace, Platform.load("fixture", path), 100)
    args = arguments(image, trace, model="sail", sail=sail)
    args.platform = path
    return args


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_sail_runs_captured_elf(sail_inputs, mul_elf, race_injector, replace, revert):
    args = sail_inputs
    image = args.elf
    hook = race_injector.file(sail_module, "run_group", image, b"not an ELF", replace=replace, revert=revert)
    result, code = cli.calculate(args)
    assert hook.fired
    assert code == 0 and result["status"] == "match", result
    assert result["reproduction"]["elf_sha256"] == digest(mul_elf.read_bytes())


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_sail_reads_captured_config(tmp_path, sail_inputs, sail, race_injector, replace, revert):
    from rvw.cosim.sail_config import query
    config = tmp_path / "base.json"
    from rvw.cosim.sail_config import read_json, build_config
    from rvw.cosim.sail import memory_regions
    from rvw.cosim.platform import Platform
    p = Platform.load("fixture", sail_inputs.platform)
    base, _ = build_config(read_json(query(sail, ["--print-default-config"], 10)), p, memory_regions(p))
    config.write_text(json.dumps(base))
    old = config.read_bytes()
    sail_inputs.sail_config = config
    hook = race_injector.file(sail_module, "prepare_config", config, b"invalid config", replace=replace, revert=revert)
    result, code = cli.calculate(sail_inputs)
    assert hook.fired
    assert code == 0 and result["status"] == "match", result
    assert result["reproduction"]["sail_config_sha256"] == digest(old)


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_changed_sail_tool_refuses_verdict(tmp_path, sail_elf, integer_platform, integer_platform_path, sail, race_injector, replace, revert):
    executable = tmp_path / "sail"
    shutil.copyfile(sail, executable)
    executable.chmod(0o755)
    trace = tmp_path / "trace.jsonl"
    generate(sail_elf, trace, integer_platform, 100)
    hook = race_injector.file(cli, "check", executable, b"changed executable", replace=replace, revert=revert)
    args = arguments(sail_elf, trace, model="sail", sail=str(executable))
    args.platform = integer_platform_path
    result, code = cli.calculate(args)
    assert hook.fired
    assert code == 3 and result["status"] == "inconclusive", result
    assert result["cause"].startswith("input_not_captured:")


def test_missing_capture_is_inconclusive(tmp_path):
    result, code = cli.calculate(arguments(tmp_path / "missing.elf", tmp_path / "missing.jsonl"))
    assert code == 3 and result["status"] == "inconclusive"
    assert result["cause"].startswith("input_not_captured:")


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_generate_does_not_publish_after_tool_change(tmp_path, elf, race_injector, monkeypatch, replace, revert):
    import sys
    from argparse import Namespace
    from rvw.cosim import generate as generation
    interpreter = tmp_path / "python"
    interpreter.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    interpreter.chmod(0o755)
    monkeypatch.setattr("rvw.cosim.inputs.sys.executable", str(interpreter))
    output = tmp_path / "ref.jsonl"
    output.write_text(json.dumps({"schema": "rvw.rvfi/1", "config": "reference"}) + "\n")
    before = output.read_bytes()
    hook = race_injector.file(generation, "record", interpreter, b"changed interpreter",
                              replace=replace, revert=revert)
    args = Namespace(cosim_action="generate", elf=elf, out=output, platform=None,
                     core="boom", max_instructions=100)
    result, code = cli.calculate(args)
    assert hook.fired
    assert code == 3 and result["status"] == "inconclusive", result
    assert output.read_bytes() == before


@pytest.mark.parametrize("name", ["library", "manifest", "dependency", "source"])
@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_spike_loads_captured_native_inputs(command_inputs, race_injector, name, replace, revert):
    from rvw.cosim import spike
    args, paths = command_inputs
    hook = race_injector.file(spike, "load_shim", paths[name], b"invalid native input", replace=replace, revert=revert)
    result, code = cli.calculate(args)
    assert hook.fired
    assert code == 0 and result["status"] == "match", result


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_sail_uses_captured_trace_after_prescan(sail_inputs, race_injector, replace, revert):
    hook = race_injector.file(cli, "check", sail_inputs.trace, b"invalid trace", replace=replace, revert=revert)
    result, code = cli.calculate(sail_inputs)
    assert hook.fired
    assert code == 0 and result["status"] == "match", result


def test_loader_cannot_substitute_a_live_shim(command_inputs, tmp_path, race_injector, monkeypatch):
    from rvw.common.capture import Capture, CaptureError
    from rvw.cosim import spike
    _, paths = command_inputs
    capture = Capture(tmp_path / "loader-inputs")
    shim = spike.capture_shim(capture, paths["library"])
    constructor = spike.C.CDLL

    def cached_loader(path, *args, **kwargs):
        if str(path) == shim["library"]["copy"]:
            return constructor(str(paths["library"]), *args, **kwargs)
        return constructor(path, *args, **kwargs)

    def substitute():
        monkeypatch.setattr(spike.C, "CDLL", cached_loader)
        monkeypatch.setattr(spike, "_MAPPING_HASHES", {}, raising=False)

    hook = race_injector.at(spike, "_load_captured", substitute, when="before")
    with pytest.raises(CaptureError, match="loader did not map the captured binary"):
        spike.load_shim(shim)
    assert hook.fired

