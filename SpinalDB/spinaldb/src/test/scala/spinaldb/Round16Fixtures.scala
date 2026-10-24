package spinaldb

import java.io.File
import spinal.core._

class Round16LiteralDesign extends Component {
  setDefinitionName("Round16Literal")
  val y = out Bits(8 bits)
  SpinalDBTestHooks.assignRound16(y)
}

class Round16ClockData extends Component {
  val io = new Bundle { val a, en, d = in Bool(); val y, z = out Bool() }
  val gclk = io.a & io.en
  val domain = ClockDomain(gclk, config = ClockDomainConfig(resetKind = BOOT))
  val logic = new ClockingArea(domain) { val r = RegNext(io.d) init False }
  io.y := gclk ^ logic.r
  io.z := logic.r
}

/** Regenerate only these small fixtures, without BOOM. */
object Round16Fixtures {
  def main(args: Array[String]): Unit = {
    val root = new File(args(0))
    root.mkdirs()
    def write(name: String)(gen: => Component): Unit =
      SpinalDB.generate(SpinalConfig(targetDirectory = new File(root, "rtl-" + name).getPath),
        new File(root, name + ".db"), DbOptions(pdg = false, blocks = false, hgldd = false))(gen)
    for (mode <- 0 to 1) {
      Round16LiteralState.mode = mode
      write(s"r16_literal$mode")(new Round16LiteralDesign)
    }
    write("r16_clockdata")(new Round16ClockData)
  }
}
