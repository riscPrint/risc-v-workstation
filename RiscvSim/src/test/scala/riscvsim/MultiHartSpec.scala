package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class MultiHartSpec extends AnyFunSuite {
  def record(order: Int, cycle: Long): RvfiRecord = RvfiRecord(BigInt(order), cycle, 0x13,
    false, false, false, 3, 2, 0, 0, 0, 0, 0, 0, 0x80000000L, 0x80000004L, 0, 0, 0, 0, 0, false)
  test("per-hart orders overlap; independent reset and completion stay explicit") {
    val path = Files.createTempFile("multi-hart", ".jsonl")
    val w = new MultiHartTrace(path.toFile, ujson.Obj("xlen" -> 64), Seq(0, 1))
    try {
      intercept[IllegalArgumentException](w.retire(0, record(0, 0)))
      w.reset(0, 0); w.reset(1, 0)
      w.retire(1, record(0, 1)); w.retire(0, record(0, 1))
      intercept[IllegalArgumentException](w.retire(0, record(2, 2)))
      w.reset(1, 2); w.retire(1, record(0, 3))
      w.complete(0, 4, Status.Pass)
      assert(w.outcome(4, 3).status == Status.Timeout)
      w.complete(1, 5, Status.Pass)
      assert(w.outcome(5, 3).status == Status.Pass)
      intercept[IllegalArgumentException](w.retire(1, record(1, 6)))
    } finally w.close()
    try {
      val lines = Files.readAllLines(path).toArray.toSeq.map(x => ujson.read(x.toString))
      assert(lines.head("schema").str == "rvw.rvfi/2")
      assert(lines.tail.map(_("capture_seq").str.toLong) == lines.tail.indices.map(_.toLong))
      assert(lines.filter(_.obj.contains("order")).map(_("order").str) == Seq("0", "0", "0"))
    } finally Files.delete(path)
  }
  test("errors and missing harts never pass") {
    val p = Files.createTempFile("multi-hart-fail", ".jsonl")
    val w = new MultiHartTrace(p.toFile, ujson.Obj(), Seq(7, 9))
    try {
      w.reset(7, 0); w.reset(9, 0)
      intercept[IllegalArgumentException](w.reset(3, 0))
      w.complete(7, 1, Status.Pass); w.complete(9, 2, Status.Error)
      assert(w.outcome(2, 0).status == Status.Error)
      intercept[IllegalArgumentException](w.memory(1, "a", "write", ujson.Obj()))
    } finally { w.close(); Files.delete(p) }
  }
  test("external events are unique and keep exact capture order") {
    val p = Files.createTempFile("multi-hart-events", ".jsonl")
    val w = new MultiHartTrace(p.toFile, ujson.Obj(), Seq(0))
    val payload = ujson.Obj("address" -> "0x0", "data" -> "0x25", "mask" -> "0xf", "source" -> "dma")
    try {
      w.reset(0, 0)
      w.memory(1, "a", "write", payload)
      intercept[IllegalArgumentException](w.memory(1, "a", "write", payload))
      intercept[IllegalArgumentException](w.memory(0, "b", "read", payload))
      w.complete(0, 2, Status.Error)
      assert(w.outcome(2, 0).status == Status.Error)
    } finally { w.close(); Files.delete(p) }
  }

  test("aggregate outcomes preserve each C1 failure category") {
    for (status <- Status.all) {
      val p = Files.createTempFile("multi-hart-status", ".jsonl")
      val w = new MultiHartTrace(p.toFile, ujson.Obj(), Seq(0, 1))
      try {
        w.reset(0, 0); w.reset(1, 0)
        w.complete(0, 1, Status.Pass); w.complete(1, 1, status)
        assert(w.outcome(1, 0).status == status)
      } finally { w.close(); Files.delete(p) }
    }
  }

  test("memory model annotations remain attached to their hart retirement") {
    val p = Files.createTempFile("multi-hart-memory-model", ".jsonl")
    val w = new MultiHartTrace(p.toFile, ujson.Obj("memory_dependencies" -> "complete"), Seq(0, 1))
    try {
      w.reset(0, 0); w.reset(1, 0)
      w.retire(1, record(0, 1), Some(ujson.Obj("id" -> "hart1-op0", "hart" -> 1, "order" -> 0)))
    } finally w.close()
    try {
      val rows = Files.readAllLines(p)
      assert(ujson.read(rows.get(3))("memory_model")("id").str == "hart1-op0")
    } finally Files.delete(p)
  }

}
