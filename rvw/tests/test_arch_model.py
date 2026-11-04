"""Checks for the standalone native gem5 model and benchmark runtime patch."""

import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("arch_model", ROOT / "Arch/model.py")
model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model)


@pytest.fixture
def description():
    return {
        "schema": "rvw.arch-core/1", "config": "test", "isa": "rv64gc", "kind": "o3",
        "cpu": {"fetchWidth": 2, "commitWidth": 2},
        "queues": [{"entries": 16, "units": [
            {"ops": ["IntAlu"], "count": 2, "latency": 1, "pipelined": True}]}],
        "predictor": {
            "tage": {"nHistoryTables": 2, "minHist": 2, "maxHist": 8,
                     "tagTableTagWidths": [0, 7, 8], "logTagTableSizes": [8, 7, 7],
                     "logUResetPeriod": 11},
            "loop": {"logSizeLoopPred": 6, "logLoopTableAssoc": 2},
            "btb": {"numEntries": 256, "associativity": 2}, "ras_entries": 16},
        "icache": {"size": "16KiB", "assoc": 4},
        "dcache": {"size": "16KiB", "assoc": 4},
        "itlb_entries": 16, "dtlb_entries": 16, "line_bytes": 64,
        "bus_bytes": 8, "memory_latency": 20,
    }


def test_description_round_trip(description, tmp_path):
    path = tmp_path / "description.json"
    path.write_text(json.dumps(description))
    assert model.load_description(path) == description


@pytest.mark.parametrize("path,value", [
    (("schema",), "rvw.arch-core/2"), (("kind",), "inorder"),
    (("config",), ""), (("isa",), "rv32im"),
    (("extra",), True), (("cpu",), {}), (("cpu", "fetchWidth"), []),
    (("cpu", "max_insts_any_thread"), 3), (("queues",), []),
    (("queues", 0, "entries"), True), (("queues", 0, "units", 0, "ops"), []),
    (("queues", 0, "units", 0, "ops"), ["IntAlu", "IntAlu"]),
    (("queues", 0, "units", 0, "count"), 0),
    (("queues", 0, "units", 0, "latency"), 0),
    (("queues", 0, "units", 0, "pipelined"), 1),
    (("predictor", "tage", "tagTableTagWidths"), [0, 7]),
    (("predictor", "tage", "logTagTableSizes"), [8, -1, 7]),
    (("predictor", "tage", "minHist"), 9),
    (("predictor", "loop", "logLoopTableAssoc"), 7),
    (("predictor", "btb", "associativity"), 3),
    (("line_bytes",), 48), (("bus_bytes",), 0),
    (("memory_latency",), float("nan")), (("memory_latency",), 0),
])
def test_invalid_description_refuses(description, path, value):
    d = copy.deepcopy(description)
    obj = d
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value
    with pytest.raises(ValueError):
        model.validate_description(d)


def test_missing_metadata_refuses(description):
    del description["schema"]
    with pytest.raises(ValueError, match="exactly"):
        model.validate_description(description)


def test_duplicate_json_key_refuses(tmp_path):
    path = tmp_path / "description.json"
    path.write_text('{"cpu": {}, "cpu": {"fetchWidth": 1}}')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        model.load_description(path)


def test_failed_main_replaces_a_stale_success(tmp_path, monkeypatch):
    output = tmp_path / "bare.json"
    output.write_text('{"exit_code": 0, "bench_stats": {"cycles": 10, "instret": 20}}')
    monkeypatch.setitem(sys.modules, "m5", SimpleNamespace(options=SimpleNamespace(outdir=tmp_path)))
    monkeypatch.setitem(sys.modules, "m5.objects", SimpleNamespace(Root=object))
    monkeypatch.setattr(sys, "argv", ["model.py", "--description", str(tmp_path / "missing.json"), "elf"])
    with pytest.raises(SystemExit) as error:
        model.main()
    assert error.value.code == 1
    result = json.loads(output.read_text())
    assert result["exit_code"] is None
    assert "error" in result
    assert "bench_stats" not in result


def make_elf(tmp_path):
    """One bare-metal load segment with no permission flags, as some linkers emit."""
    data = bytearray(1024)
    data[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HHIQQQ", data, 16, 2, 243, 1, model.RAM_BASE, 64, 128)
    struct.pack_into("<HHHH", data, 54, 56, 1, 64, 3)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 0, 0, model.RAM_BASE, model.RAM_BASE,
                     len(data), len(data), 4096)
    # Null section, symbol table, string table.
    struct.pack_into("<IIQQQQIIQQ", data, 192, 0, 2, 0, 0, 512, 120, 2, 0, 8, 24)
    strings = b"\0tohost\0tohost_exit\0setStats\0bench_stats\0"
    data[768:768 + len(strings)] = strings
    struct.pack_into("<IIQQQQIIQQ", data, 256, 0, 3, 0, 0, 768, len(strings), 0, 0, 1, 0)
    syms = {}
    for i, (name, size) in enumerate((("tohost", 8), ("tohost_exit", 16),
                                     ("setStats", 16), ("bench_stats", 16)), 1):
        addr = model.RAM_BASE + i * 32
        struct.pack_into("<IBBHQQ", data, 512 + i * 24, strings.index(name.encode()),
                         0, 0, 1, addr, size)
        syms[name] = (addr, size)
    path = tmp_path / "kernel.riscv"
    path.write_bytes(data)
    return path, data, syms


def test_bare_elf_without_segment_permissions(tmp_path):
    path, _, syms = make_elf(tmp_path)
    assert model.elf_symbols(path) == syms


@pytest.mark.parametrize("damage", ["truncated", "wrong_machine", "undefined", "short_counters", "outside_ram"])
def test_invalid_elf_refuses(tmp_path, damage):
    path, data, _ = make_elf(tmp_path)
    if damage == "truncated":
        data = data[:40]
    elif damage == "wrong_machine":
        struct.pack_into("<H", data, 18, 62)
    elif damage == "undefined":
        struct.pack_into("<H", data, 512 + 24 + 6, 0)
    elif damage == "short_counters":
        struct.pack_into("<Q", data, 512 + 4 * 24 + 16, 8)
    else:
        struct.pack_into("<Q", data, 64 + 24, 0)
    path.write_bytes(data)
    with pytest.raises(ValueError):
        model.elf_symbols(path)


@pytest.fixture
def simulation(monkeypatch):
    """The drain manager requires tryDrain after its Finished drain event."""
    syms = {"setStats": (10, 8), "tohost_exit": (20, 8),
            "tohost": (30, 8), "bench_stats": (40, 16)}
    state = SimpleNamespace(tick=0, pc=0, calls=[], try_count=0, drained=False,
                            events=[(10, "simpoint starting point found"),
                                    (10, "simpoint starting point found"),
                                    (20, "simpoint starting point found"),
                                    (0, "Finished drain")], exit_value=1, counters=(100, 200))

    def simulate(ticks):
        state.calls.append(ticks)
        if state.events:
            state.pc, cause = state.events.pop(0)
            state.tick += min(10, ticks)
        else:
            state.tick += ticks
            cause = "simulate() limit reached"
        return SimpleNamespace(getCause=lambda: cause)

    def try_drain():
        state.try_count += 1
        state.drained = state.try_count >= 2
        return state.drained

    manager = SimpleNamespace(isDrained=lambda: state.drained, tryDrain=try_drain)
    m5 = SimpleNamespace(curTick=lambda: state.tick, simulate=simulate,
                         stats=SimpleNamespace(reset=lambda: None, dump=lambda: None),
                         memWriteback=lambda root: None)
    monkeypatch.setitem(sys.modules, "m5", m5)
    monkeypatch.setitem(sys.modules, "m5.objects", SimpleNamespace(
        Root=SimpleNamespace(getInstance=lambda: None)))
    monkeypatch.setitem(sys.modules, "_m5.drain", SimpleNamespace(
        DrainManager=SimpleNamespace(instance=lambda: manager)))

    def read_guest(shm, addr, size):
        return (struct.pack("<Q", state.exit_value) if addr == 30
                else struct.pack("<QQ", *state.counters))

    monkeypatch.setattr(model, "read_guest", read_guest)
    tracker = SimpleNamespace(getCurrentPcCountPair=lambda: SimpleNamespace(get_pc=lambda: state.pc))
    state.system = SimpleNamespace(pc_tracker=tracker, shared_backstore="unused")
    state.syms = syms
    return state


def test_run_requires_counters_and_drains_with_remaining_budget(simulation):
    s = simulation
    result = model.run_bare(s.system, s.syms, 100)
    assert result["exit_code"] == 0
    assert result["bench_stats"] == {"cycles": 100, "instret": 200}
    assert s.try_count == 2
    assert s.calls == [100, 90, 80, 70]


@pytest.mark.parametrize("failure", ["timeout", "drain_timeout", "missing_roi", "extra_roi", "zero_counters", "even_exit"])
def test_run_refuses_incomplete_evidence(simulation, failure):
    s = simulation
    if failure == "timeout":
        s.events.clear()
    elif failure == "drain_timeout":
        s.events.pop()
    elif failure == "missing_roi":
        s.events.pop(0)
    elif failure == "extra_roi":
        s.events.insert(0, (10, "simpoint starting point found"))
    elif failure == "zero_counters":
        s.counters = (0, 200)
    else:
        s.exit_value = 2
    with pytest.raises(ValueError):
        model.run_bare(s.system, s.syms, 100)
    assert s.tick <= 100


def test_guest_failure_keeps_nonzero_exit_code(simulation):
    simulation.exit_value = 7
    result = model.run_bare(simulation.system, simulation.syms, 100)
    assert result["exit_code"] == 3


def test_patch_runtime_and_refuse_changed_source(tmp_path):
    script = ROOT / "Arch/bench/rt/patch_syscalls.sh"
    source = tmp_path / "syscalls.c"
    source.write_text("void setStats(int enable)\n{\n}\n  tohost = (uintptr_t)magic_mem;\n")
    run = subprocess.run(["sh", str(script), str(source)], capture_output=True, text=True)
    assert run.returncode == 0
    assert "static void setStats_rt" in run.stdout
    assert "bench_stats[0] = counters[0]" in run.stdout
    assert "bench_stats[1] = counters[1]" in run.stdout
    assert "return 0; /* no HTIF console host */" in run.stdout
    source.write_text(run.stdout)
    assert subprocess.run(["sh", str(script), str(source)], capture_output=True).returncode != 0
    source.write_text("void setStats_changed(int enable)\n")
    assert subprocess.run(["sh", str(script), str(source)], capture_output=True).returncode != 0


def test_empty_benchmark_selection_refuses(tmp_path):
    source = tmp_path / "src/common"
    source.mkdir(parents=True)
    (source / "syscalls.c").write_text("unused")
    run = subprocess.run(["make", "-C", str(ROOT / "Arch/bench"),
                          f"SRC={source.parent}", "BENCHES="], capture_output=True, text=True)
    assert run.returncode != 0
    assert "BENCHES must not be empty" in run.stderr


def test_project_data_preserves_historical_queue_placement():
    """The old model's broad fallback changed timing. Keep its correction explicit."""
    data_dir = ROOT / "examples/boom/arch"
    baseline = json.loads((data_dir / "large.json").read_text())
    disjoint = json.loads((data_dir / "large-disjoint.json").read_text())
    fallback = baseline["queues"][1]["units"][3]["ops"]
    assert {"IntAlu", "IntMult", "MemRead", "MemWrite", "FloatAdd", "System"} <= set(fallback)
    assert not {"IntAlu", "IntMult", "MemRead", "MemWrite", "FloatAdd", "System"} & set(disjoint["queues"][1]["units"][3]["ops"])
    baseline["queues"][1]["units"][3]["ops"] = disjoint["queues"][1]["units"][3]["ops"]
    assert baseline == disjoint
    for name in ("small", "medium", "large", "mega", "large-disjoint"):
        model.validate_description(json.loads((data_dir / (name + ".json")).read_text()))


def test_roi_accepts_sign_extended_rv32_pc(simulation):
    s = simulation
    s.events = [(0xffffffff0000000a, 'simpoint starting point found'),
                (0xffffffff0000000a, 'simpoint starting point found'),
                (0xffffffff00000014, 'simpoint starting point found'),
                (0, 'Finished drain')]
    assert model.run_bare(s.system, s.syms, 100)['exit_code'] == 0


@pytest.mark.parametrize('override', [
    {'numFTQEntries': 0}, {'numFTQEntries': True}, {'minInstSize': 4},
    {'minInstSize': 0}, {'fetchTargetWidth': 32}, {'maxFTPerCycle': 0},
    {'maxTakenPredPerCycle': 0}, {'decoupledFrontEnd': 'true'},
])
def test_invalid_riscv_decoupled_settings(description, override):
    description['cpu'].update(decoupledFrontEnd=True, minInstSize=2,
                              fetchTargetWidth=64, numFTQEntries=16)
    description['cpu'].update(override)
    with pytest.raises(ValueError, match=r'cpu\.'):
        model.validate_description(description)


def test_riscv_decoupled_settings(description):
    description['cpu'].update(decoupledFrontEnd=True, minInstSize=2,
                              fetchTargetWidth=64, numFTQEntries=16)
    model.validate_description(description)


def test_decoupled_frontend_refuses_minor(description):
    description.update(kind='minor', isa='rv32im', queues=[], predictor=None)
    description['cpu'].update(decoupledFrontEnd=True, minInstSize=2,
                              fetchTargetWidth=64, numFTQEntries=16)
    with pytest.raises(ValueError, match='requires O3'):
        model.validate_description(description)
