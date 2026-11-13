package spinalkonata

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class TraceSpec extends AnyFunSuite {
  test("future ordering, implicit lane ends, flush, dependency and quiet observation tail") {
    val path = Files.createTempFile("kanata", ".log")
    val w = new KanataWriter(path.toFile)
    w.record(0, Fetch(4, 99, "thread")); w.record(0, Label(4, "pc\ttext\nclean"))
    w.record(0, Enter(4, "F"))
    w.record(2, Enter(4, "X"))
    w.record(2, Enter(4, "wait", "1")); w.record(3, Leave(4, "wait", "1"))
    w.record(1, Fetch(8, 100)); w.record(1, Enter(8, "F"))
    w.record(1, Dependency(8, 4)); w.record(3, Flush(8))
    w.record(4, Retire(4)); w.seal(7); w.close()
    val text = Files.readString(path)
    assert(text.startsWith("Kanata\t0004\nC=\t0\nI\t4\t99\tthread\n"))
    assert(text.contains("pc text clean"))
    assert(text.indexOf("I\t8") < text.indexOf("S\t4\t0\tX"))
    assert(text.contains("E\t4\t0\tF\nS\t4\t0\tX"))
    assert(text.contains("W\t8\t4\t0"))
    assert(text.contains("S\t4\t1\twait"))
    assert(text.contains("E\t4\t1\twait"))
    assert(text.contains("R\t8\t0\t1"))
    assert(text.endsWith("C\t3\n"))
  }
  test("explicit causes, replay and predicated physical commits") {
    val path = Files.createTempFile("kanata-events", ".log")
    val w = new KanataWriter(path.toFile)
    w.record(0, Fetch(0, 0))
    w.record(1, Stall("issue", StallCause.OperandWait))
    w.record(1, Stall("memory", StallCause.LoadMiss, "inferred"))
    w.record(1, Replay(0, "ordering"))
    w.record(2, Commit(0, predicatedOff = true)); w.close()
    val text = Files.readString(path)
    assert(text.contains("#rvw\t1\tstall\tissue\toperand_wait\tmeasured"))
    assert(text.contains("#rvw\t1\tstall\tmemory\tload_miss\tinferred"))
    assert(text.contains("#rvw\t1\treplay\t0\tordering\tmeasured"))
    assert(text.contains("#rvw\t1\tcommit\t0\tpredicated_off\nR\t0\t0\t0"))
  }
  test("observed predictions round-trip through the production reader") {
    val path = Files.createTempFile("kanata-prediction", ".log")
    val w = new KanataWriter(path.toFile)
    w.record(0, Fetch(0, 0))
    w.record(1, PredictionOutcome(0, "p", "direction", "taken", "not_taken",
      Some(4), Some(3), Some(true), Some(false), Some("user")))
    w.record(1, PredictionOutcome(0, "ras", "return", "0x10", "0x10"))
    w.record(2, Flush(0)); w.close()
    import scala.sys.process._
    val python = """import sys
sys.path.insert(0, sys.argv[1])
from collections import Counter
from rvw.perf.kanata import read
from rvw.perf.events import event_report
r = event_report(read(sys.argv[2]), Counter())['predictions']
assert r['outcomes'] == 2
assert r['by_context'][0]['incorrect'] == 1
assert r['by_context'][0]['recovery_cycles']['sum'] == 4
assert r['by_context'][1]['recovery_cycles']['unknown'] == 1
print('prediction events checked')
"""
    assert(Seq("python3", "-c", python, new java.io.File("../rvw/src").getCanonicalPath,
      path.toString).!!.trim == "prediction events checked")
  }
  test("prediction writer refuses malformed and duplicate observations") {
    for (event <- Seq(
      PredictionOutcome(0, "p", "direction", "true", "false"),
      PredictionOutcome(0, "p", "target", "-1", "0"),
      PredictionOutcome(0, "p", "return", "0", "0", Some(-1)),
      PredictionOutcome(0, "p", "direction", "taken", "taken", context = Some("bad\tcontext")))) {
      val w = new KanataWriter(Files.createTempFile("kanata-invalid-prediction", ".log").toFile)
      w.record(0, Fetch(0, 0)); w.record(1, event)
      intercept[IllegalArgumentException](w.seal(1)); w.close()
    }
    val w = new KanataWriter(Files.createTempFile("kanata-duplicate-prediction", ".log").toFile)
    val event = PredictionOutcome(0, "p", "direction", "taken", "taken")
    w.record(0, Fetch(0, 0)); w.record(1, event); w.record(1, event)
    intercept[IllegalArgumentException](w.seal(1)); w.close()
  }
  test("invalid and late events fail closed, while bounded open instructions stay open") {
    val path = Files.createTempFile("kanata-open", ".log")
    val w = new KanataWriter(path.toFile)
    w.record(0, Fetch(1, 1)); w.seal(0)
    intercept[IllegalArgumentException](w.record(0, Retire(1)))
    w.close()
    assert(!Files.readString(path).contains("R\t"))
    val bad = new KanataWriter(Files.createTempFile("kanata-bad", ".log").toFile)
    bad.record(0, Retire(22))
    intercept[IllegalArgumentException](bad.seal(0))
    bad.close()
  }
  test("real Spinal simulation demo generates six instructions, one discard and five retires") {
    val path = Files.createTempFile("kanata-demo", ".log")
    Demo.main(Array(path.toString))
    val lines = Files.readString(path).linesIterator.toSeq
    assert(lines.count(_.startsWith("#rvw\t1\tstall\tpipeline\tstructural\tmeasured")) == 3)
    assert(lines.count(_.endsWith("\tpredicated_off")) == 1)
    assert(lines.count(_.endsWith("\tarchitectural")) == 4)
    assert(lines.count(_.startsWith("I\t")) == 6)
    assert(lines.count(_.startsWith("#rvw\t1\tprediction\t")) == 2)
    assert(lines.contains("#rvw\t1\tprediction\t1\tdemo_bimodal\tdirection\tnot_taken\ttaken\t2\t1\ttrue\tfalse\tdemo"))
    assert(lines.count(l => l.startsWith("R\t") && l.endsWith("\t0")) == 5)
    assert(lines.count(l => l.startsWith("R\t") && l.endsWith("\t1")) == 1)
    // Read the actual simulator output with the production Python parser and event reporter.
    import scala.sys.process._
    val python = """import sys
sys.path.insert(0, sys.argv[1])
from collections import Counter
from rvw.perf.kanata import read
from rvw.perf.events import event_report
t = read(sys.argv[2])
c = Counter(i.end for i in t.instructions.values() if i.end is not None and not i.flushed)
r = event_report(t, c)
assert r['stall_causes']['measured_cycles'] == 3
assert r['commit_kinds']['architectural_total'] == 4
assert r['commit_kinds']['predicated_off_observed'] == 1
assert sum(c.values()) == 5
(e,) = r['predictions']['effects']
assert e['overall']['outcomes'] == 2 and e['overall']['correct'] == 1
assert e['by_warmup']['true']['incorrect'] == 1 and e['steady_state']['accuracy'] == 1.0
print('pipeline events checked')
"""
    val source = new java.io.File("../rvw/src").getCanonicalPath
    assert(Seq("python3", "-c", python, source, path.toString).!!.trim == "pipeline events checked")
  }
}
