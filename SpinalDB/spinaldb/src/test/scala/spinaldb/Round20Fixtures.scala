package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

/** Round-20 reviewer probes, with caller-owned output paths. */
class Round20Ports(swapped: Boolean) extends Component {
  setDefinitionName("Round20Ports")
  val a, b = in Bool()
  a.setName("_zz_a"); b.setName("_zz_b")
  val y = out Bool()
  y := (if (swapped) b && !a else a && !b)
}

class Round20Sync extends Component {
  val a = in UInt(2 bits)
  val en = in Bool()
  val y = out Bits(8 bits)
  val m = Mem(Bits(8 bits), 4)
  m.initBigInt(Seq(1, 2, 3, 4).map(BigInt(_)))
  y := m.readSync(a, en)
}

object Round20Fixtures {
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    def write(name: String, options: DbOptions)(gen: => Component): Unit = {
      val dir = root.resolve(name); Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory = dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile, options)(gen)
    }
    val lean = DbOptions(pdg = false, blocks = false, hgldd = false)
    for (n <- 0 to 1) write(s"ports$n", lean.copy(sourceRoots = Nil))(new Round20Ports(n == 1))
    write("main-only", lean)(new Round20Ports(false))
    write("required", lean.copy(sourceRoots = Seq(root.resolve("missing"))))(new Round20Ports(false))
    write("sync", lean.copy(sourceRoots = Nil))(new Round20Sync)
  }
}
