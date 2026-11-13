"""Round 10 (cosim): the Spike shim must never clear a pending bit that software set (SSIP/STIP or
an mip write). It injects only the interrupt inputs the platform declares (`irq_inputs`), restores
their earlier value after the step, and a software interrupt must come from the reference's own state."""
from model_fixtures import load_shim
import json
from pathlib import Path

import pytest

from rvw.cosim.checker import check
from model_fixtures import generate
from rvw.cosim import platform as platform_module
from rvw.cosim.platform import Platform
from model_fixtures import Spike
from rvw.cosim.trace import record

SSIP = (1 << 63) | 1


def core_trace(elf, platform, tmp_path):
    """Spike's own trace, with its non-retired interrupted instruction turned into the standalone
    trap event a core such as BOOM records."""
    ref = tmp_path / "ref.jsonl"
    generate(elf, ref, platform, limit=100)
    rows = [json.loads(x) for x in ref.read_text().splitlines()]
    rows = [r for r in rows if not ("order" in r and r["trap"])]
    for i, r in enumerate(r for r in rows if "order" in r):
        r["order"] = i
    return rows


def run(tmp_path, rows, elf, platform):
    path = tmp_path / "core.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    model = Spike(platform, elf)
    try:
        return check(path, model, platform)
    finally:
        model.close()


def mip_read(rows, model_elf):
    return next(r for r in rows if r.get("insn") == "0x344024f3")   # csrr s1, mip


def test_software_set_ssip_survives_interrupt_entry(tmp_path, ssip_elf, integer_platform):
    platform = integer_platform
    rows = core_trace(ssip_elf, platform, tmp_path)
    assert any(r.get("event") == "trap" and int(r["cause"], 16) == SSIP for r in rows)
    read = mip_read(rows, ssip_elf)
    assert int(read["rd_wdata"], 16) & 2
    result = run(tmp_path, rows, ssip_elf, platform)
    assert result["status"] == "match", result
    assert result["trace_complete"] and result["synchronized"] == 0


def test_lost_ssip_is_a_mismatch(tmp_path, ssip_elf, platform):
    rows = core_trace(ssip_elf, platform, tmp_path)
    mip_read(rows, ssip_elf)["rd_wdata"] = "0x0"
    result = run(tmp_path, rows, ssip_elf, platform)
    assert result["status"] == "mismatch", result
    assert result["mismatch"]["disassembly"].startswith("csrr")
    assert "rd_wdata" in result["mismatch"]["differences"]


def raw_trace(elf, platform, inject_at, cause):
    """A trace in which the core takes interrupt `cause` at `inject_at`, built by forcing it into
    Spike (bypassing the platform's input filter): what an injecting reference would accept."""
    model = Spike(platform, elf)
    rows = [{"schema": "rvw.rvfi/1", "xlen": platform.xlen, "isa": platform.isa,
             "core": "fixture", "config": "test", "elf": str(elf)}]
    pc, intr_next, order = platform.reset_pc, False, 0
    try:
        for cycle in range(100):
            if pc == model.elf.symbols[inject_at] and cause:
                e = model._step_raw(cause)
                assert e["trap"] and e["intr"], e
                rows.append({"event": "trap", "cycle": cycle, "intr": True, "cause": hex(e["cause"]), "tval": "0x0"})
                pc, intr_next, cause = e["pc_next"], True, 0
                continue
            e = model._step_raw()
            rows.append(record(e, order, intr=intr_next))
            order += 1
            intr_next = bool(e["trap"])
            pc = e["pc_next"]
            if e["mem_wmask"] and e["mem_addr"] == model.elf.symbols["tohost"]:
                rows.append({"event": "end", "cycle": cycle, "status": "pass"})
                return rows
        raise AssertionError("fixture did not terminate")
    finally:
        model.close()


def test_software_interrupt_needs_the_references_own_pending_bit(tmp_path, ssip_elf, platform):
    """A core that takes SSIP before software set it: the reference has nothing pending, so SSIP
    must not be injected, and the trap event is a mismatch."""
    rows = raw_trace(ssip_elf, platform, "before_set_site", SSIP)
    result = run(tmp_path, rows, ssip_elf, platform)
    assert result["status"] == "mismatch", result
    assert result["mismatch"]["actual"].get("intr") is True


@pytest.mark.parametrize("code", [1, 9])
def test_injected_bit_restores_the_software_bit(seip_elf, platform, code):
    """SSIP and SEIP set by software, then that bit injected for one step through the shim itself
    (interrupts disabled, so nothing is taken): afterwards the software-set bits are still pending."""
    model = Spike(platform, seip_elf)
    try:
        while model._step_raw()["pc_next"] != model.elf.symbols["inject_site"]:
            pass
        e = model._step_raw((1 << 63) | code)
        assert not e["trap"]
        e = model.step()
        assert e["pc"] == model.elf.symbols["read_site"]
        assert e["rd_wdata"] & 0x202 == 0x202, hex(e["rd_wdata"])
        # Software clears both bits: the injected input left nothing of its own behind.
        model.step()
        e = model.step()
        assert e["pc"] == model.elf.symbols["cleared_site"]
        assert e["rd_wdata"] & 0x202 == 0, hex(e["rd_wdata"])
    finally:
        model.close()


def test_injected_input_is_withdrawn_after_the_step(ssip_elf, platform):
    """MTIP (an input; software cannot set it) injected for one step is not pending afterwards."""
    model = Spike(platform, ssip_elf)
    try:
        while model._step_raw()["pc_next"] != model.elf.symbols["before_set_site"]:
            pass
        assert not model.step(interrupt=(1 << 63) | 7)["trap"]   # mie.MTIE is off
        # mie has only SSIE; MTIP must be gone, so the handler later reads exactly SSIP.
        for _ in range(50):
            e = model.step()
            if e["pc"] == model.elf.symbols["mip_site"]:
                assert e["rd_wdata"] == 0x2, hex(e["rd_wdata"])
                return
        raise AssertionError("handler not reached")
    finally:
        model.close()


def test_irq_inputs_are_validated(tmp_path):
    base = json.loads((Path(platform_module.__file__).parent / "configs" / "boom.json").read_text())
    assert Platform.load("boom").irq_inputs == [3, 7, 9, 11]
    for bad in ([1], [64], "3", [3, 3], [-1], [True]):
        cfg = dict(base, irq_inputs=bad)
        f = tmp_path / "p.json"
        f.write_text(json.dumps(cfg))
        with pytest.raises(ValueError):
            Platform.load("boom", f)
    cfg = dict(base, irq_inputs=[7])
    f = tmp_path / "p.json"
    f.write_text(json.dumps(cfg))
    assert Platform.load("boom", f).irq_inputs == [7]


# --------------------------------------------------------------------------------------------------
# A shim that was not rebuilt (old behaviour, e.g. clearing a software-set SEIP) is refused.

import hashlib
import shutil
import subprocess

from rvw.cosim import spike as spike_module

PREFIX = Path("/opt/homebrew")


def _compile(source, out, define=None):
    cmd = [shutil.which("c++") or "c++", "-std=c++20", "-O2", "-fPIC", "-shared", f"-I{PREFIX}/include"]
    if define is not None:
        cmd.append(f'-DRVW_SHIM_SOURCE_SHA256="{define}"')
    lib = next((PREFIX / "lib" / n for n in ("libriscv.so", "libriscv.dylib", "libriscv.a")
                if (PREFIX / "lib" / n).exists()), None)
    if lib is None:
        pytest.skip("Spike library not found")
    cmd += [str(source), str(lib), f"{PREFIX}/lib/libdisasm.a", f"{PREFIX}/lib/libfesvr.a",
            f"-Wl,-rpath,{PREFIX}/lib", "-o", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _current_manifest():
    built = Path(spike_module.__file__).resolve().parents[4] / "Cosim/build/librvw_spike.so.manifest.json"
    return json.loads(built.read_text())


def _stale(tmp_path, name, source_text, define=None, manifest=None):
    src = tmp_path / f"{name}.cc"
    src.write_text(source_text)
    lib = _compile(src, tmp_path / f"{name}.so", define)
    Path(str(lib) + ".manifest.json").write_text(json.dumps(manifest if manifest is not None else _current_manifest()))
    return lib


def test_old_shim_without_version_is_refused(tmp_path, elf, platform):
    current = spike_module.SHIM_SOURCE.read_text()
    old = current[:current.index("#ifndef RVW_SHIM_SOURCE_SHA256")] + current[current.index('const char* rvw_error()'):]
    old = old.replace('const char* rvw_error()', 'extern "C" {\nconst char* rvw_error()', 1)
    lib = _stale(tmp_path, "old", old)   # an old binary next to a current manifest
    with pytest.raises(ValueError, match="rebuild with Cosim/build.sh"):
        Spike(platform, elf, library=str(lib))


def test_shim_built_from_another_source_is_refused(tmp_path, elf, platform):
    source = spike_module.SHIM_SOURCE.read_text()
    other = hashlib.sha256(b"older spike_shim.cc").hexdigest()
    lib = _stale(tmp_path, "other", source, define=other)
    with pytest.raises(ValueError, match="rebuild with Cosim/build.sh"):
        Spike(platform, elf, library=str(lib))
    # The manifest alone cannot vouch for it either: a version-1 manifest is refused before loading.
    Path(str(lib) + ".manifest.json").write_text(json.dumps({**_current_manifest(), "shim_version": 1}))
    with pytest.raises(ValueError, match="version 1.*rebuild with Cosim/build.sh"):
        Spike(platform, elf, library=str(lib))
    Path(str(lib) + ".manifest.json").unlink()
    with pytest.raises(ValueError, match="no readable build manifest.*rebuild with Cosim/build.sh"):
        Spike(platform, elf, library=str(lib))


def test_edited_source_refuses_the_built_shim(tmp_path, elf, platform):
    edited = tmp_path / "spike_shim.cc"
    edited.write_text(spike_module.SHIM_SOURCE.read_text() + "\n// edited\n")
    default = Path(spike_module.__file__).resolve().parents[4] / "Cosim/build/librvw_spike.so"
    with pytest.raises(ValueError, match="another spike_shim.cc.*rebuild with Cosim/build.sh"):
        load_shim(default, edited)
    assert load_shim(default) is not None   # the real build matches the real source


def test_cli_refuses_a_stale_shim_with_exit_2(tmp_path, elf, platform, monkeypatch, capsys):
    from rvw.cli import main
    source = spike_module.SHIM_SOURCE.read_text()
    lib = _stale(tmp_path, "stale", source, define=hashlib.sha256(b"x").hexdigest())
    trace = tmp_path / "t.jsonl"
    generate(elf, trace, platform, limit=20)
    monkeypatch.setenv("RVW_SPIKE_SHIM", str(lib))
    try:
        code = main(["cosim", "check", "--elf", str(elf), "--core", "boom", "--trace", str(trace), "--json"])
    except SystemExit as e:
        code = e.code
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and out["status"] == "error", out
    assert "rebuild with Cosim/build.sh" in out["message"]
