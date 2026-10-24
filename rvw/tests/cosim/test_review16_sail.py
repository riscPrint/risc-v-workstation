"""Sail must execute the selected ISA and confirm it before comparing a trace."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from cosim_build import _build
from rvw.cosim.checker import check
from model_fixtures import generate
from model_fixtures import Sail
from rvw.cosim.sail import memory_regions
from rvw.cosim import sail_config


@pytest.fixture(scope="session")
def mul_elf(tmp_path_factory):
    return _build(tmp_path_factory, Path(__file__).with_name("program_mul.S"), march="rv64im_zicsr_zifencei")


def mul_trace(tmp_path, platform, mul_elf):
    p = replace(platform, isa="rv64im_zicsr_zifencei", reference_isa=None,
                sail_overrides={}, csr_masks={}, aligned_mem=False, mode_after_change=False,
                illegal_insn_tval="insn")
    trace = tmp_path / "mul.jsonl"
    assert generate(mul_elf, trace, p, 100)["termination"] == "pass"
    return p, trace


@pytest.mark.parametrize("selection", ["isa", "reference_isa", "override", "config", "enabled"])
def test_sail_enforces_platform_m_extension(tmp_path, platform, mul_elf, sail, selection):
    p, trace = mul_trace(tmp_path, platform, mul_elf)
    config = None
    enabled = selection == "enabled"
    if not enabled:
        p = replace(p, isa="rv64i_zicsr_zifencei")
        if selection == "reference_isa":
            p = replace(p, isa="rv64im_zicsr_zifencei", reference_isa=p.isa)
        elif selection == "override":
            p = replace(p, sail_overrides={"extensions": {"M": {"supported": True}, "Zmmul": {"supported": True}}})
        elif selection == "config":
            config = tmp_path / "base.json"
            base = sail_config.read_json(sail_config.query(sail, ["--print-default-config"], 10))
            base, _ = sail_config.build_config(base, p, memory_regions(p))
            base["extensions"]["M"]["supported"] = True
            base["extensions"]["Zmmul"]["supported"] = True
            config.write_text(json.dumps(base))
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        rows[0]["isa"] = p.isa
        trace.write_text("\n".join(map(json.dumps, rows)) + "\n")
    model = Sail(p, mul_elf, trace, sail, config=config)
    try:
        result = check(trace, model, p)
    finally:
        model.close()
    assert result["status"] == ("match" if enabled else "mismatch"), result
    if not enabled:
        assert result["mismatch"]["expected"]["cause"] == "0x2"
        assert "trap" in result["mismatch"]["differences"]


@pytest.fixture(scope="session")
def sail_base(sail):
    return sail_config.read_json(sail_config.query(sail, ["--print-default-config"], 10))


@pytest.mark.parametrize("isa,xlen", [
    ("rv64i_zicsr_zifencei", 64),
    ("rv64im_zicsr_zifencei", 64),
    ("rv64gc", 64),
    ("rv64i_zca", 64),
    ("rv64ifd_zicsr_zca_zcd", 64),
    ("rv32if_zicsr_zca_zcf", 32),
    ("rv32if_zicsr_zca", 32),
    ("rv64ifd_zicsr_zca", 64),
    ("rv64imafdc_zicsr_zifencei_zba_zbb_zbs_zicntr_zihpm", 64),
    ("rv32i_zicsr_zifencei", 32),
    ("rv32imafdc_zicsr_zifencei", 32),
])
def test_native_sail_confirms_selected_isa(tmp_path, platform, sail, isa, xlen):
    p = replace(platform, isa=isa, xlen=xlen, reference_isa=None, sail_overrides={})
    path = sail_config.prepare_config(p, sail, None, tmp_path, memory_regions(p), 10, env=None,
                                      default_config=sail_config.query(sail, ["--print-default-config",
                                          *(["--rv32"] if p.xlen == 32 else [])], 10))
    config = json.loads(path.read_text())
    assert config["base"]["xlen"] == xlen
    assert config["extensions"]["M"]["supported"] == ("m" in sail_config.isa_extensions(isa, xlen))
    assert config["extensions"]["H"]["supported"] is False
    assert config["extensions"]["V"]["support_level"] == "Disabled"


@pytest.mark.parametrize("count", [0, 1, 8, 16, 17, 64])
def test_native_sail_applies_platform_pmp_count(tmp_path, platform, sail, count):
    p = replace(platform, pmp_regions=count)
    path = sail_config.prepare_config(p, sail, None, tmp_path, memory_regions(p), 10, env=None,
                                      default_config=sail_config.query(sail, ["--print-default-config",
                                          *(["--rv32"] if p.xlen == 32 else [])], 10))
    assert json.loads(path.read_text())["memory"]["pmp"]["usable_count"] == count


@pytest.fixture(scope="session")
def pmp_counts_elf(tmp_path_factory):
    return _build(tmp_path_factory, Path(__file__).with_name("program_pmp_counts.S"), march="rv64i_zicsr")


@pytest.mark.parametrize("count", [0, 1, 8, 16, 17, 64])
def test_native_sail_pmp_csr_effects_match_selected_count(tmp_path, platform, sail, pmp_counts_elf, count):
    p = replace(platform, pmp_regions=count, isa="rv64i_zicsr", reference_isa=None,
                aligned_mem=False, csr_masks={}, illegal_insn_tval="insn")
    trace = tmp_path / "pmp.jsonl"
    generate(pmp_counts_elf, trace, p, 100)
    model = Sail(p, pmp_counts_elf, trace, sail)
    try:
        result = check(trace, model, p)
    finally:
        model.close()
    assert result["status"] == "match" and result["trace_complete"], result
    assert result["end_status"] == ("fail" if count == 0 else "pass")
    if count:
        writes = {r["rd"]: r["rd_wdata"] for r in map(json.loads, trace.read_text().splitlines()) if "rd" in r}
        assert int(writes[10], 0) == (0x1234 if count >= 8 else 0)
        assert int(writes[11], 0) == (0x1234 if count >= 9 else 0)


def test_build_config_applies_platform_and_keeps_explicit_tuning(platform, sail_base):
    c, _ = sail_config.build_config(sail_base, platform, memory_regions(platform))
    assert c["base"]["xlen"] == 64 and not c["base"]["E"]
    assert c["memory"]["pmp"]["count"] == 16 and c["memory"]["pmp"]["usable_count"] == 8
    assert c["memory"]["physaddr_bits"] == 32
    assert c["memory"]["regions"] == memory_regions(platform)
    assert c["base"]["xtval_nonzero"]["illegal_instruction"] is False
    assert c["extensions"]["M"]["mutable_misa"] is False
    assert c["extensions"]["S"]["supported"] and c["extensions"]["U"]["supported"]
    assert not c["extensions"]["H"]["supported"]
    assert not c["extensions"]["Sv32"]["supported"]
    assert c["extensions"]["Sv39"]["supported"]
    assert not c["extensions"]["Sv48"]["supported"] and not c["extensions"]["Sv57"]["supported"]
    assert c["extensions"]["Svade"]["supported"]
    assert c["extensions"]["S"]["interrupts"]["software"]["supported"]
    for access in ("load_store", "amo", "lrsc"):
        assert c["memory"]["misaligned"]["exceptions"][access] == {"Some": "AlignmentException"}


@pytest.mark.parametrize("reported", ["", "rv64i", "rv64im_zicsr_zifencei", "rv32i_zicsr_zifencei", "unreadable config"])
def test_unconfirmed_effective_isa_is_an_error(tmp_path, platform, sail_base, monkeypatch, reported):
    p = replace(platform, isa="rv64i_zicsr_zifencei", reference_isa=None, sail_overrides={})
    monkeypatch.setattr(sail_config, "query", lambda executable, args, timeout:
                        json.dumps(sail_base) if "--print-default-config" in args else reported)
    with pytest.raises(ValueError, match="Sail.*(?:confirm|XLEN)"):
        sail_config.prepare_config(p, "fixture", None, tmp_path, memory_regions(p), 1, env=None, default_config=json.dumps(sail_base))


def test_unconfirmed_config_stops_execution_and_cleans_up(tmp_path, platform, mul_elf, sail_base, monkeypatch):
    p, trace = mul_trace(tmp_path, platform, mul_elf)
    paths = []
    def query(executable, args, timeout, *, env=None):
        if "--print-default-config" in args:
            return json.dumps(sail_base)
        paths.append(Path(args[1]))
        return "rv64i"  # missing selected instruction extensions
    def must_not_execute(*args, **kwargs):
        pytest.fail("Sail executed before its config was confirmed")
    monkeypatch.setattr(sail_config, "query", query)
    monkeypatch.setattr("rvw.cosim.sail.run_group", must_not_execute)
    with pytest.raises(ValueError, match="Sail effective ISA cannot be confirmed"):
        Sail(p, mul_elf, trace, "fixture", default_config=json.dumps(sail_base))
    assert paths and all(not path.exists() for path in paths)


@pytest.mark.parametrize("isa", ["rv64iv", "rv64ih", "rv64e", "rv64i_zmadeup", "rv64i2p1", "rv32i"])
def test_unsupported_isa_is_refused(platform, sail_base, isa):
    with pytest.raises(ValueError, match="Sail cannot confirm ISA"):
        sail_config.build_config(sail_base, replace(platform, isa=isa, reference_isa=None), [])


def test_config_probe_uses_timeout_and_process_group(monkeypatch):
    from rvw.common.proc import Result
    seen = []
    def run(argv, **options):
        seen.append((argv, options))
        return Result(124, timed_out=True)
    monkeypatch.setattr(sail_config, "run_group", run)
    with pytest.raises(ValueError, match="within 0.1 s"):
        sail_config.query("sail", ["--print-isa-string"], 0.1)
    assert seen == [(["sail", "--print-isa-string"], {"timeout": 0.1, "capture": True})]


def test_native_sail_refuses_incompatible_privileged_config(tmp_path, platform, sail, sail_base):
    config = tmp_path / "base.json"
    # The full default trigger configuration needs H. This checker supports MSU only.
    config.write_text(json.dumps(sail_base))
    with pytest.raises(ValueError, match="Sail cannot confirm config"):
        sail_config.prepare_config(replace(platform, sail_overrides={}), sail, config, tmp_path, memory_regions(platform), 10, env=None, default_config=None)


def test_sail_json_comments_do_not_damage_strings():
    assert sail_config.read_json('{/* comment */"url": "https://example//x", // line\n"x": 1}') == {
        "url": "https://example//x", "x": 1}
