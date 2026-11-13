package spinalkonata

import spinal.core._
import spinal.core.sim._

/** Three registers, a global hold, and a deliberately discarded instruction (ID 2). */
class DemoPipeline extends Component {
  val io = new Bundle {
    val valid = in Bool()
    val id = in UInt(16 bits)
    val advance = in Bool()
  }
  val fValid = RegInit(False)
  val xValid = RegInit(False)
  val wValid = RegInit(False)
  val fId, xId, wId = Reg(UInt(16 bits)) init(0)
  when(io.advance) {
    fValid := io.valid; fId := io.id
    xValid := fValid; xId := fId
    wValid := xValid && xId =/= 2; wId := xId
  }
  val tags = new PipelineTags
  tags.fetch(io.valid && io.advance, io.id, () => s"${io.id.toLong.toHexString}: demo class=demo")
  tags.enter(io.valid && io.advance, io.id, "F")
  tags.enter(fValid && io.advance, fId, "X")
  tags.enter(xValid && io.advance && xId =/= 2, xId, "W")
  tags.flush(xValid && io.advance && xId === 2, xId)
  tags.stall(!io.advance && fValid, "pipeline", StallCause.Structural)
  // Branch outcomes at write-back for IDs 1 and 3: ID 1 mispredicts while cold.
  val isBranch = wValid && io.advance && (wId === 1 || wId === 3)
  val recovery = UInt(8 bits); recovery := 2
  val wrongPath = UInt(8 bits); wrongPath := 1
  val taken = Bool(); taken := True
  val aliased = Bool(); aliased := False
  tags.direction(isBranch, wId, "demo_bimodal", wId === 3, taken, recovery = Some(recovery),
    wrongPath = Some(wrongPath), warmup = Some(wId === 1), alias = Some(aliased), context = () => Some("demo"))
  tags.commit(wValid && io.advance, wId, wId === 4)
}

object Demo {
  def main(args: Array[String]): Unit = {
    val out = new java.io.File(args.headOption.getOrElse("demo.log"))
    SimConfig.withVerilator.compile(new DemoPipeline).doSim { dut =>
      dut.io.valid #= false; dut.io.id #= 0; dut.io.advance #= false
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(5)
      val writer = new KanataWriter(out)
      var cycle = 0L
      dut.clockDomain.onSamplings { dut.tags.sample(writer, cycle); cycle += 1 }
      for (id <- 0 until 6) {
        dut.io.valid #= true; dut.io.id #= id; dut.io.advance #= true
        dut.clockDomain.waitSampling()
        if (id == 3) {
          dut.io.advance #= false
          dut.clockDomain.waitSampling(3)
        }
      }
      dut.io.valid #= false; dut.io.advance #= true
      dut.clockDomain.waitSampling(5)
      writer.close()
    }
    println(s"Demo trace: ${out.getAbsolutePath}")
  }
}
