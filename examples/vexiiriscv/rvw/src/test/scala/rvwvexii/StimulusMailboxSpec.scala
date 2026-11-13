package rvwvexii

import org.scalatest.funsuite.AnyFunSuite
import riscvsim.{Cli, StimulusMailbox}
import scala.collection.mutable.ArrayBuffer

class StimulusMailboxSpec extends AnyFunSuite {
  private def file(events: String): java.io.File = {
    val f = java.io.File.createTempFile("stimulus", ".json")
    f.deleteOnExit()
    java.nio.file.Files.writeString(f.toPath, s"""{"schema":"rvw.stimulus/1","events":[$events]}""")
    f
  }
  private def event(step: Int, level: Boolean, settle: Int = 0) =
    s"""{"id":"e$step","kind":"device","payload":{"step":$step,"kind":"plic-level","source":1,"level":$level,
       |"settle_ticks":$settle,"request_symbol":"stimulus_step","ack_symbol":"stimulus_ack"}}""".stripMargin

  test("events are driven in order and acknowledged after settling") {
    val stimulus = StimulusMailbox.load(file(event(2, true, 3) + "," + event(5, false)))
    val driven = ArrayBuffer.empty[Boolean]
    val acks = ArrayBuffer.empty[(Long, Long)]
    var now = 0L
    val m = new StimulusMailbox(stimulus, e => driven += e("level").bool, s => acks += ((now, s)))
    assert(!m.request(10, BigInt(5)))           // not the next event
    assert(m.request(10, BigInt(2)))
    assert(!m.request(11, BigInt(5)))           // waits for the acknowledgement
    for (c <- 10L to 13L) { now = c; m.tick(c) }
    assert(acks == Seq((13L, 2L)))
    assert(m.request(20, BigInt(5)))
    now = 20; m.tick(20)
    assert(driven == Seq(true, false) && m.complete && m.served == 2)
    assert(stimulus.sha256.length == 64)
  }

  test("malformed stimulus files are refused") {
    intercept[Cli.UsageError](StimulusMailbox.load(file(event(3, true) + "," + event(2, false))))
    intercept[Cli.UsageError](StimulusMailbox.load(file("")))
  }
}
