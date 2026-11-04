import json
import hashlib
import xml.etree.ElementTree as ET

import pytest

from rvw.results import (RunResult, SchemaError, SuiteResults, TestEntry, Verdict, failure_signature,
                         find_results, load_results, load_run, load_verdict, normalize_message,
                         save_results, save_run, to_junit, validate, write_json, write_junit)

RUN = {
    "schema": "rvw.run/1", "core": "boom", "config": "small", "elf": "/x/rv64ui-p-add",
    "elf_sha256": "ab", "seed": 1, "max_cycles": 200000, "mem_latency": None, "status": "pass",
    "fail_code": None, "message": None, "cycles": 1234, "instret": 456, "wall_s": 3.2,
    "source": {"core_rev": "0cb0b69", "core_dirty": False}, "tools": {"verilator": "5.049"},
    "artifacts": {"log": "run.log"}, "replay": "run.sh run ...", "metrics": {"roi_cycles": 1000},
}


def test_run_round_trip(tmp_path):
    r = RunResult.from_dict(RUN)
    assert r.cycles == 1234 and r.metrics == {"roi_cycles": 1000}
    save_run(r, tmp_path)
    assert json.loads((tmp_path / "result.json").read_text()) == RUN
    assert load_run(tmp_path) == r


@pytest.mark.parametrize("bad,msg", [
    ({"status": "weird"}, "status"),
    ({"schema": "rvw.run/2"}, "schema"),
    ({"cycles": "12"}, "cycles"),
    ({"seed": True}, "seed"),
])
def test_run_validation(bad, msg):
    with pytest.raises(SchemaError, match=msg):
        RunResult.from_dict({**RUN, **bad})


def _results(tests, suite="riscv-tests", config="small"):
    return SuiteResults(run_id="r1", suite=suite, core="boom", config=config, created="2026-10-20T00:00:00Z",
                        source={"core_rev": "abc", "core_dirty": False}, tests=tests)


@pytest.mark.parametrize("invalid,escaped", [("\x1b", r"\x1b"), ("\x00", r"\x00"),
                                            ("\ud800", r"\ud800"), ("\ufffe", r"\ufffe")])
def test_junit_escapes_invalid_xml_in_text_and_attributes(tmp_path, invalid, escaped):
    value = f"{invalid}[31mfailed{invalid}[0m"
    res = _results([TestEntry(value, "fail", signature=value, run=value,
                             extra={"message": value})], suite=value, config=value)
    res.run_id = value
    res.created = value
    res.core = value
    res.source["core_rev"] = value
    tree = to_junit(res)
    parsed = ET.fromstring(ET.tostring(tree.getroot(), encoding="utf-8"))
    for element in parsed.iter():
        for text in [*element.attrib.values(), element.text or ""]:
            assert invalid not in text
    assert escaped in parsed.find("testsuite/testcase/failure").text
    assert escaped in parsed.find("testsuite/testcase").get("name")
    path = write_junit(res, tmp_path / "junit.xml")
    ET.parse(path)


def test_junit_keeps_valid_xml_text():
    message = "line 1\t<&>\nline 2\r\u00e9\U0001f600"
    res = _results([TestEntry("a", "fail", signature="fail:1", extra={"message": message})])
    failure = to_junit(res).getroot().find("testsuite/testcase/failure")
    assert message in failure.text


def test_results_round_trip_and_find(tmp_path):
    res = _results([TestEntry("a", "pass", seed=1, cycles=10, metrics={"ipc": 0.5}),
                    TestEntry("b", "fail", seed=2, signature="fail:3", extra={"cached": True})])
    save_results(res, tmp_path / "set" / "riscv-tests" / "small")
    save_results(_results([], suite="vm"), tmp_path / "set" / "vm" / "small")
    back = load_results(tmp_path / "set" / "riscv-tests" / "small")
    assert back.tests == res.tests and back.tests[1].extra == {"cached": True}
    assert back.counts() == {"pass": 1, "fail": 1}
    found = find_results(tmp_path / "set")
    assert [r.suite for r in found] == ["riscv-tests", "vm"]
    assert [r.suite for r in find_results(tmp_path / "set" / "vm" / "small")] == ["vm"]


def test_results_validation():
    d = _results([TestEntry("b", "fail")]).to_dict()
    assert any("signature" in e for e in validate(d))
    d["tests"][0]["signature"] = "fail:1"
    assert validate(d) == []
    assert validate({"schema": "nope"}) == ["unknown schema 'nope'"]


def test_verdict_round_trip(tmp_path):
    v = Verdict("reject", new_failures=[{"suite": "s", "id": "a", "signature": "fail:1"}], reasons=["1 new failure"])
    write_json(tmp_path / "verdict.json", v.to_dict())
    assert load_verdict(tmp_path) == v
    assert not v.accepted
    with pytest.raises(SchemaError):
        Verdict.from_dict({"schema": "rvw.verdict/1", "verdict": "maybe"})
    i = Verdict("inconclusive", inconclusive=[{"id": "a", "why": "harness error"}], reasons=["1 inconclusive result"])
    assert Verdict.from_dict(i.to_dict()) == i and not i.accepted
    assert (Verdict("accept").exit_code, v.exit_code, i.exit_code) == (0, 1, 3)


@pytest.mark.parametrize("status,code,msg,sig", [
    ("pass", None, None, None),
    ("fail", 3, None, "fail:3"),
    ("timeout", None, "hit max cycles 200000", "timeout"),
    ("assert", None, "Assertion failed at /work/boom/src/main/scala/boom/lsu/lsu.scala:1241 cycle 98765",
     "assert:lsu.scala:1241"),
    ("assert", None, "%Error: /tmp/sim/BoomSimTop.v:12345: Assertion failed in TOP.core.rob at time 4567",
     "assert:BoomSimTop.v:12345"),
    # RVFI monitor errors: the code, whether or not the monitor's message line was captured
    ("rvfi_error", None, "riscv-formal monitor error 105 at pc 0x80000124", "rvfi_error:105"),
    ("rvfi_error", None, "riscv-formal RVFI monitor error 105", "rvfi_error:105"),
    ("rvfi_error", None, "riscv-formal RVFI monitor error 105: rd_wdata mismatch", "rvfi_error:105"),
    ("rvfi_error", None, "monitor flagged something", "rvfi_error:sha256:" + hashlib.sha256(b"monitor flagged something").hexdigest()),
    # testbench exceptions keep their type, not only the top frame
    ("assert", None, "java.lang.IllegalStateException: bad at boom.sim.Mem.read(Mem.scala:42)",
     "assert:IllegalStateException@Mem.scala:42"),
    ("assert", None, "java.lang.NullPointerException: null at boom.sim.Mem.read(Mem.scala:42)",
     "assert:NullPointerException@Mem.scala:42"),
    ("assert", None, "scala.MatchError: 3 (of class java.lang.Integer)",
     "assert:sha256:" + hashlib.sha256(b"scala.MatchError: 3 (of class java.lang.Integer)").hexdigest()),
    ("assert", None, "FAILURE rob head (rob.scala:L812)", "assert:rob.scala:812"),
    ("assert", None, "Error: plain text", "assert:sha256:" + hashlib.sha256(b"Error: plain text").hexdigest()),
    ("error", None, "", "error"),
])
def test_signatures(status, code, msg, sig):
    assert failure_signature(status, code, msg) == sig


def test_wall_clock_timeout_signature_and_conclusive():
    from rvw.results import run_signature
    assert failure_signature("timeout", None, "x", wall_clock=True) == "timeout:wall-clock"
    assert run_signature({**RUN, "status": "timeout", "wall_clock_timeout": True}) == "timeout:wall-clock"
    assert run_signature({**RUN, "status": "timeout", "message": "no result after 200000 cycles"}) == "timeout"
    assert run_signature({**RUN, "status": "rvfi_error", "message": "no text", "details": {"rvfi_errcode": 7}}) == "rvfi_error:7"
    assert TestEntry("a", "fail", signature="fail:3").conclusive
    assert TestEntry("a", "timeout", signature="timeout").conclusive
    assert not TestEntry("a", "timeout", signature="timeout:wall-clock").conclusive
    assert not TestEntry("a", "error", signature="error:x").conclusive
    assert not TestEntry("a", "timeout", signature="timeout", extra={"synthesized": True}).conclusive


def test_load_run_is_the_c1_loader(tmp_path):
    with pytest.raises(FileNotFoundError, match="no result.json"):
        load_run(tmp_path)
    (tmp_path / "run.log").write_text("x")
    save_run(RunResult.from_dict({**RUN, "status": "fail", "fail_code": 3}), tmp_path)
    r = load_run(tmp_path)
    assert r.dir == tmp_path.resolve() and r.failed and r.get("fail_code") == 3 and r.get("nope", 1) == 1
    assert r.get("metrics") == {"roi_cycles": 1000}
    assert r.artifact("log") == tmp_path.resolve() / "run.log" and r.artifact("wave") is None


def test_signature_stable_across_seeds_and_paths():
    a = failure_signature("error", None, "Exception in /a/b/Foo.v:10 seed=1234567 addr 0xdeadbeef\nmore")
    b = failure_signature("error", None, "Exception in /c/Foo.v:99 seed=7654321 addr 0x80001000")
    assert a == b
    assert normalize_message("rob_3 index 7") == "rob_3 index 7"  # small numbers carry meaning


def test_junit(tmp_path):
    res = _results([TestEntry("a", "pass", wall_s=1.0), TestEntry("b", "fail", signature="fail:3", wall_s=2.0),
                    TestEntry("c", "error", signature="error:boom")])
    p = write_junit(res, tmp_path / "junit.xml")
    root = ET.parse(p).getroot()
    assert root.get("tests") == "3" and root.get("failures") == "1" and root.get("errors") == "1"
    ts = root.find("testsuite")
    assert ts.get("name") == "riscv-tests.small"
    cases = ts.findall("testcase")
    assert cases[1].find("failure").get("message") == "fail:3"
    assert cases[2].find("error") is not None
    assert to_junit([res, res]).getroot().get("tests") == "6"


@pytest.mark.parametrize('status,details,conclusive', [
    ('assert', {'concurrent': True}, False),
    ('rvfi_error', {'concurrent': True}, False),
    ('pass', {'serial_rerun': {'attributed': False}}, False),
    ('assert', {'concurrent': True, 'serial_rerun': {'attributed': True}}, True),
    ('assert', {'concurrent': False}, True),
    ('pass', {'concurrent': True}, True),
    ('assert', None, True),
])
def test_c1_and_c3_share_concurrent_attribution(status, details, conclusive):
    run = RunResult.from_dict({'schema': 'rvw.run/1', 'status': status, 'details': details})
    entry = TestEntry.from_dict({'id': 'A', 'status': status, 'details': details})
    assert (run.why_inconclusive is None) == entry.conclusive == conclusive


def test_standalone_json_uses_one_checked_read(tmp_path, monkeypatch):
    from rvw.common import capture
    path = tmp_path / 'result.json'
    path.write_text('{"schema":"rvw.run/1","status":"pass"}')
    alias = tmp_path / 'alias.json'
    alias.symlink_to(path)
    def no_copy(*args, **kwargs):
        raise AssertionError('parse-only reads must not create a Capture')
    monkeypatch.setattr(capture.Capture, '__init__', no_copy)
    reads = []
    real_read = capture.os.read
    def read(fd, size):
        reads.append(capture.os.fstat(fd).st_ino)
        return real_read(fd, size)
    monkeypatch.setattr(capture.os, 'read', read)
    run = load_run(alias)
    assert run.status == 'pass' and run.path == tmp_path
    assert reads == [path.stat().st_ino] * 2
