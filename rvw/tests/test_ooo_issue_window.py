from types import SimpleNamespace
import pytest
from rvw.ooo.issue_window import IssueWindow

pytestmark = pytest.mark.fast


def test_busy_oldest_line_prevents_reuse_of_younger_holes():
    window = IssueWindow(4, 2)
    window.advance(0)
    slow = SimpleNamespace(done=10)
    window.append(slow)
    window.append(SimpleNamespace(done=2))
    window.advance(1)
    window.append(SimpleNamespace(done=2))
    window.advance(3)
    assert window.full()
    window.advance(10)
    assert window.full()
    window.advance(11)
    assert not window.full()


def test_partial_line_consumes_full_line_and_wakeup_releases_it():
    window = IssueWindow(2, 2)
    window.advance(0)
    window.append(SimpleNamespace(done=None))
    assert not window.full()  # second lane in this rename group
    window.advance(1)
    assert window.full()
    window.lines[0][0].done = 2
    window.advance(3)
    assert not window.full()


def test_compacting_policy_increases_pressure_on_dependent_line():
    from dataclasses import replace
    from test_ooo import cfg
    from rvw.ooo.core import Instruction, simulate
    config = replace(cfg(), rob_entries=32, issue_entries=4, rename_width=2,
                     latencies={"alu": 1, "divide": 20}, issue_width=2, commit_width=4)
    ops = [Instruction("divide", (), 1), Instruction("alu", (1,), 2)]
    ops += [Instruction("alu", (), 3) for _ in range(20)]
    associative = simulate(ops, config, backend="python")
    compacting = simulate(ops, replace(config, issue_queue_policy="compacting"), backend="python")
    assert compacting["cycles"] > associative["cycles"]
    assert compacting["events"]["issue_full"] > associative["events"].get("issue_full", 0)


def test_compacting_policy_rejects_partial_capacity():
    from dataclasses import replace
    from test_ooo import cfg
    with pytest.raises(ValueError, match="whole rename lines"):
        replace(cfg(), issue_entries=3, rename_width=2, issue_queue_policy="compacting")
