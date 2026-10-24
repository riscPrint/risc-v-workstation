"""C8 races in the standalone cosim smoke command."""
import hashlib
import json

import pytest

from race_injection import race_injector
from rvw.cosim.spike import SHIM_SOURCE


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def smoke_module():
    import importlib.util
    path = SHIM_SOURCE.parent / "smoke.py"
    spec = importlib.util.spec_from_file_location("cosim_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_smoke_uses_captured_elfs(tmp_path, elf, smoke_module, race_injector, monkeypatch, replace, revert):
    source = tmp_path / "isa"
    source.mkdir()
    image = source / "rv64ui-p-one"
    image.write_bytes(elf.read_bytes())
    second = source / "rv64ui-p-two"
    second.write_bytes(elf.read_bytes())
    output = tmp_path / "smoke.json"
    monkeypatch.setattr("sys.argv", ["smoke.py", "--isa-dir", str(source), "--out", str(output)])
    hook = race_injector.file(smoke_module, "generate", image, b"replaced ELF", replace=replace, revert=revert)
    code = smoke_module.main()
    assert hook.fired
    rows = json.loads(output.read_text())
    assert code == 0 and len(rows) == 2 and all(row["status"] == "match" for row in rows), rows
    assert rows[0]["elf_sha256"] == rows[1]["elf_sha256"] == digest(elf.read_bytes())
    assert all(row["capture_row"] == 0 for row in rows) and rows[0]["capture"]["schema"] == "rvw.capture/1"


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_smoke_captures_batch_before_first_run(tmp_path, elf, smoke_module, race_injector, monkeypatch, replace, revert):
    source = tmp_path / "isa"
    source.mkdir()
    for name in ("one", "two"):
        (source / f"rv64ui-p-{name}").write_bytes(elf.read_bytes())
    output = tmp_path / "smoke.json"
    monkeypatch.setattr("sys.argv", ["smoke.py", "--isa-dir", str(source), "--out", str(output)])
    hook = race_injector.file(smoke_module, "generate", source / "rv64ui-p-two", b"replaced ELF", replace=replace, revert=revert)
    code = smoke_module.main()
    assert hook.fired
    rows = json.loads(output.read_text())
    assert code == 0 and all(row["status"] == "match" for row in rows), rows
    assert len(rows[0]["capture"]["files"]) > 2
