package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class WriterCheckpointSpec extends AnyFunSuite {
  test("restore C2 prefix, counters, IRQ and pending late trap") {
    val baseline = Files.createTempFile("c2-base", ".jsonl").toFile
    val resumed = Files.createTempFile("c2-resume", ".jsonl").toFile
    val header = ujson.Obj("xlen" -> 32)
    val writer = new RvfiTraceWriter(baseline, header)
    writer.irq(2, 0x80)
    writer.trapNextCycle(3, 7, false)
    val state = ujson.read(ujson.write(writer.checkpoint()))
    def suffix(w: RvfiTraceWriter): Unit = {
      w.cycle(Nil, BigInt(0x1234))
      w.irq(4, 0)
      intercept[IllegalStateException](w.irq(3, 0))
      w.end(8, "pass")
      intercept[IllegalArgumentException](w.checkpoint())
      w.close()
    }
    suffix(writer)
    val fresh = new RvfiTraceWriter(resumed, header, resume = Some(state))
    suffix(fresh)
    assert(Files.readAllBytes(baseline.toPath).sameElements(Files.readAllBytes(resumed.toPath)))
    assert(fresh.records == writer.records && fresh.orderGaps == writer.orderGaps)
    val changed = ujson.read(ujson.write(state))
    changed("position") = "0"
    intercept[IllegalArgumentException](new RvfiTraceWriter(resumed, header, resume = Some(changed)))
    intercept[IllegalArgumentException](new RvfiTraceWriter(resumed, ujson.Obj("xlen" -> 64), resume = Some(state)))
  }
}
