package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class InterruptScheduleSpec extends AnyFunSuite {
  test("schedule preserves levels through masked and pending intervals") {
    val s = InterruptSchedule.parse("1:0x0,100:0x880,200:0x8,300:0x0")
    assert(s.levelsAt(99) == 0)
    assert(s.levelsAt(100) == 0x880)
    assert(s.levelsAt(199) == 0x880)
    assert(s.levelsAt(200) == 8)
    assert(s.levelsAt(300) == 0)
    assert(InterruptSchedule.parse(s.text) == s)
  }
  test("unsupported adapter inputs refuse before simulation") {
    val options = Map("elf" -> "test", "out" -> "out", "irq-schedule" -> "1:0x8")
    intercept[Cli.UsageError](Cli.job(options, ToyAdapter, new java.io.File(".")))
    val job = Cli.job(options.updated("irq-schedule", "1:0x0"), ToyAdapter, new java.io.File("."))
    assert(new Driver(ToyAdapter).replay(job).contains("--irq-schedule 1:0x0"))
    intercept[Cli.UsageError](Cli.job(options.updated("irq-schedule", "1:0x0,10:0x0") +
      ("max-cycles" -> "10"), ToyAdapter, new java.io.File(".")))
  }
  test("invalid and ambiguous schedules refuse") {
    for (s <- Seq("", "0:0x0", "2:0x0", "1:0x0,1:0x8", "1:0x0,3:0x8,2:0x0",
      "1:8", "1:0x-1", "1:0x10000000000000000", "1:0x0,9223372036854775808:0x0"))
      intercept[Cli.UsageError](InterruptSchedule.parse(s))
  }
}
