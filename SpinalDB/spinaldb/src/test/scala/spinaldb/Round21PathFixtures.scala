package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

class Round21Delay extends Component {
  val a = in Bool()
  val y = out Bool()
  var prev = a
  for (i <- 0 until 1100) {
    val r = RegNext(prev) init(False)
    r.setName(s"stage_$i")
    prev = r
  }
  val left, right = Bool()
  left := prev; right := prev
  left.dontSimplifyIt(); right.dontSimplifyIt()
  y := left ^ right
}
object Round21PathFixtures {
  def main(args: Array[String]): Unit = {
    val dir = Paths.get(args(0)).resolve("delay"); Files.createDirectories(dir)
    SpinalDB.generate(SpinalConfig(targetDirectory = dir.resolve("rtl").toString),
      dir.resolve("design.db").toFile,
      DbOptions(pdg=false, blocks=false, hgldd=false, sourceRoots=Nil))(new Round21Delay)
  }
}
