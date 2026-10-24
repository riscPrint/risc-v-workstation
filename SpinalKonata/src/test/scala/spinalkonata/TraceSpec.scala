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
    assert(lines.count(_.startsWith("I\t")) == 6)
    assert(lines.count(l => l.startsWith("R\t") && l.endsWith("\t0")) == 5)
    assert(lines.count(l => l.startsWith("R\t") && l.endsWith("\t1")) == 1)
  }
}
