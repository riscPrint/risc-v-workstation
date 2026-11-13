package rvwformal
import spinal.core._
import spinal.lib._

/** Small real library component for the database autocheck smoke run. */
class AutocheckFifo extends Component {
  val io = new Bundle {
    val push = slave(Stream(Bits(2 bits)))
    val pop = master(Stream(Bits(2 bits)))
  }
  val fifo = StreamFifo(Bits(2 bits), 2)
  io.push >> fifo.io.push
  fifo.io.pop >> io.pop
}

object AutocheckDatabase {
  def main(args: Array[String]): Unit = {
    spinaldb.SpinalDB.generate(
      SpinalConfig(defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC), targetDirectory = args(1)),
      new java.io.File(args(0)), spinaldb.DbOptions(pdg = false, blocks = false, hgldd = false))(
      new AutocheckFifo)
  }
}
