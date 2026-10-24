"""Real Spike roundtrip through Registry, using the small synthetic assembly fixture."""
import json
import hashlib

import pytest

from race_injection import race_injector
from rvw.mcp.registry import Registry


def call(registry, name, arguments):
    _, started, error = registry.call_json(name, arguments)
    assert not error, started
    _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 60})
    assert not error and status["status"] == "done", status
    return status["result"]


def test_cosim_generate_and_check_match_cli(elf, tmp_path, rvw):
    registry, problems = Registry.discover({"cosim"})
    assert not problems
    try:
        trace = tmp_path / "trace.jsonl"
        args = {"elf": str(elf), "core": "boom", "out": str(trace), "max_instructions": 200}
        call(registry, "cosim_generate", args)  # both parity calls capture an existing reference trace
        generated = call(registry, "cosim_generate", args)
        assert generated == rvw("cosim", "generate", "--elf", elf, "--core", "boom", "--out", trace,
                                "--max-instructions", 200, "--json")[2]
        assert generated["termination"] == "pass"
        checked = call(registry, "cosim_check", {"elf": str(elf), "core": "boom", "trace": str(trace), "history": 3})
        assert checked == rvw("cosim", "check", "--elf", elf, "--core", "boom", "--trace", trace, "--history", 3, "--json")[2]
        assert checked["status"] == "match"
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        row = next(r for r in rows if r.get("rd", 0))
        row["rd_wdata"] = hex(int(row["rd_wdata"], 16) ^ 4)
        trace.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        mismatch = call(registry, "cosim_check", {"elf": str(elf), "core": "boom", "trace": str(trace)})
        assert mismatch["status"] == "mismatch" and "rd_wdata" in mismatch["mismatch"]["differences"]
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_cosim_published_capture_has_no_private_paths(elf, tmp_path, race_injector, replace, revert):
    from rvw.cosim.cli import execute_json
    from rvw.cosim.inputs import Inputs

    image = tmp_path / "program.elf"
    original = elf.read_bytes()
    image.write_bytes(original)
    hook = race_injector.file(Inputs, "metadata", image, b"changed ELF", replace=replace, revert=revert)
    result = execute_json("generate", elf=image, core="boom", out=tmp_path / "trace.jsonl",
                          max_instructions=200)
    assert hook.fired and result["status"] == "generated", result
    capture = result["reproduction"]["capture"]

    def check(value):
        if isinstance(value, dict):
            assert "copy" not in value
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(capture)
    row = next(row for row in capture["files"] if row["source"] == str(image))
    assert row["resolved"] == str(image)
    assert row["sha256"] == hashlib.sha256(original).hexdigest()
    assert row["size"] == len(original)
    assert result["reproduction"]["elf_sha256"] == row["sha256"]


def test_cosim_errors_preserve_cli_json(tmp_path, rvw):
    registry, _ = Registry.discover({"cosim"})
    try:
        result = call(registry, "cosim_check", {"elf": str(tmp_path / "missing.elf"), "core": "boom", "trace": str(tmp_path / "missing.jsonl")})
        assert result == rvw("cosim", "check", "--elf", tmp_path / "missing.elf", "--core", "boom",
                             "--trace", tmp_path / "missing.jsonl", "--json")[2]
        assert result["status"] == "inconclusive"
    finally:
        registry.jobs.shutdown()


def run_job(registry, name, arguments):
    """(is_error, payload): a refused call, or the finished job's status."""
    _, started, error = registry.call_json(name, arguments)
    if error:
        return True, started
    _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 60})
    assert not error and status["status"] in ("done", "failed"), status
    return status["status"] == "failed", status


def test_cosim_check_never_runs_a_sail_argument(elf, tmp_path, monkeypatch):
    """Review finding 8: the sail argument named any executable the server would run."""
    marker = tmp_path / "ran"
    fake = tmp_path / "fake-sail"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\n")
    fake.chmod(0o755)
    registry, _ = Registry.discover({"cosim"})
    try:
        failed, payload = run_job(registry, "cosim_check", {"elf": str(elf), "core": "boom", "model": "sail",
                                                            "trace": str(tmp_path / "t.jsonl"), "sail": str(fake)})
        assert failed and "sail" in json.dumps(payload)
        assert not marker.exists()
    finally:
        registry.jobs.shutdown()


def test_cosim_generate_refuses_to_overwrite_elf_or_other_files(elf, tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("keep me\n")
    elf_bytes = elf.read_bytes()
    registry, _ = Registry.discover({"cosim"})
    try:
        for out, message in ((elf, "ELF"), (other, "not a C2 trace"), (tmp_path, "directory")):
            failed, payload = run_job(registry, "cosim_generate", {"elf": str(elf), "core": "boom", "out": str(out)})
            result = payload.get("result", payload)
            assert result["status"] == "error" and message in result["message"], result
        assert elf.read_bytes() == elf_bytes and other.read_text() == "keep me\n"
        trace = tmp_path / "trace.jsonl"
        for _ in range(2):   # an existing C2 trace may be replaced
            failed, payload = run_job(registry, "cosim_generate", {"elf": str(elf), "core": "boom", "out": str(trace),
                                                                   "max_instructions": 200})
            assert payload["result"]["status"] == "generated"
    finally:
        registry.jobs.shutdown()


def test_strict_sync_switches_one_kind(csr_elf, tmp_path, rvw):
    from test_review_fixes import core_trace, write
    from rvw.cosim.platform import Platform
    rows, _ = core_trace(csr_elf, Platform.load("boom"), edits={"misa_site": lambda v: v & ~0x2})
    trace = write(tmp_path, rows)
    base = ("cosim", "check", "--elf", csr_elf, "--core", "boom", "--trace", trace, "--json")
    assert rvw(*base)[2]["status"] == "match"
    code, _, result = rvw(*base, "--strict-sync", "csr")[:3]
    assert result["status"] == "mismatch" and result["sync_enabled"] == ["counter", "irq", "mmio"]
    assert "--strict-sync csr" in result["reproduction"]["replay"]
    assert rvw(*base, "--strict-sync", "counter,mmio")[2]["status"] == "match"
    assert rvw(*base, "--strict")[2]["sync_enabled"] == []
    registry, _ = Registry.discover({"cosim"})
    try:
        mcp = call(registry, "cosim_check", {"elf": str(csr_elf), "core": "boom", "trace": str(trace), "strict_sync": ["csr"]})
        assert mcp["status"] == "mismatch" and mcp["sync_enabled"] == ["counter", "irq", "mmio"]
    finally:
        registry.jobs.shutdown()
