"""Fail-closed UVM result parsing and pinned dependency checks."""
import io
import tarfile
from pathlib import Path

import pytest

from rvw.results import load_results
from rvw.sim import uvm
from rvw.common.proc import Result


def complete():
    return "\n".join(f"RVW_UVM_PASS {name}" for name in uvm.FEATURES) + "\nRVW_UVM_DONE\n"


def test_positive_requires_complete_unique_evidence():
    log = complete()
    assert uvm.evidence(log, 0, False)
    for bad in (log.replace("RVW_UVM_DONE", ""), log.replace("RVW_UVM_PASS rvfi\n", ""),
                log + "RVW_UVM_PASS rvfi\n", log + "UVM_ERROR : 1\n",
                log + "UVM_FATAL @ 10: test [FAIL] mismatch\n",
                log + "UVM_ERROR source.sv(2) @ 1: test [ERROR] bad\n"):
        assert not uvm.evidence(bad, 0, False)
    assert not uvm.evidence(log, 1, False)
    assert not uvm.evidence(log, 0, True)


def test_negative_requires_specific_rvfi_failure():
    log = "UVM_FATAL @ 10: test [RVFI] load observation mismatch\n"
    assert uvm.evidence(log, -6, False, negative=True)
    assert not uvm.evidence(log, 0, False, negative=True)
    assert not uvm.evidence(log, -6, True, negative=True)
    assert not uvm.evidence("segmentation fault", -11, False, negative=True)
    assert not uvm.evidence(log + complete(), -6, False, negative=True)


def test_reject_archive_before_extraction(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="checksum"):
        uvm.unpack(archive, tmp_path / "lib")
    assert not (tmp_path / "lib").exists()


def test_license_mismatch(tmp_path, monkeypatch):
    archive = tmp_path / "test.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in uvm.LICENSES:
            member = tarfile.TarInfo("root/" + name)
            member.size = 3
            tar.addfile(member, io.BytesIO(b"bad"))
    monkeypatch.setattr(uvm, "ARCHIVE_SHA256", uvm.sha(archive))
    with pytest.raises(ValueError, match="licence or notice"):
        uvm.unpack(archive, tmp_path / "lib")


def test_build_failure_is_c3_error(tmp_path, monkeypatch):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(b"wrong")
    monkeypatch.setattr(uvm.shutil, "which", lambda _: "/bin/false")
    monkeypatch.setattr(uvm, "run_group", lambda *a, **k: Result(0, stdout="fake version"))
    out = tmp_path / "out"
    report = uvm.run(out, archive=archive)
    assert report["tests"][0]["status"] == "error"
    loaded = load_results(out)
    assert not loaded.tests[0].conclusive
    with pytest.raises(FileExistsError):
        uvm.run(out, archive=archive)


@pytest.mark.parametrize("kwargs", [{"seed": 0}, {"seeds": 0}, {"seed": 2**31},
                                    {"timeout": float("nan")}, {"timeout": -1}])
def test_bad_request_has_no_output(tmp_path, kwargs):
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        uvm.run(out, **kwargs)
    assert not out.exists()


def test_regress_cli():
    from rvw.cli import main
    with pytest.raises(SystemExit) as result:
        main(["regress", "uvm", "--help"])
    assert result.value.code == 0


@pytest.mark.parametrize('fault,diagnostic', [
    ('ral','[RAL] read or prediction mismatch'),
    ('pins','[PINS] interrupt/debug pin mismatch')])
def test_control_and_ral_faults_need_expected_failure(fault,diagnostic):
    assert uvm.evidence(diagnostic,1,False,negative=fault)
    assert not uvm.evidence(diagnostic,0,False,negative=fault)
    assert not uvm.evidence(diagnostic,1,True,negative=fault)
    assert not uvm.evidence('unrelated crash',1,False,negative=fault)
    assert not uvm.evidence(diagnostic+'\nRVW_UVM_DONE',1,False,negative=fault)
