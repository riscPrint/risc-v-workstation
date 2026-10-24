package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

class Round21Area extends Component {
  val a = in Bool()
  val y = out Bool()
  val logic = new Area { val r = RegNext(a) init(False) }
  y := logic.r
}
class Round21OverrideArea extends Component {
  val a = in Bool()
  val y = out Bool()
  val logic = new Area {
    val r = RegNext(a) init(False)
    override def getName(): String = "hidden"
  }
  y := logic.r
}
trait Round21UserOverride extends Area { override def getName(): String = "hidden" }
class Round21TraitArea extends Component {
  val a = in Bool()
  val y = out Bool()
  val logic = new Round21UserOverride { val r = RegNext(a) init(False) }
  y := logic.r
}
class Round21SuperArea extends Component {
  val a = in Bool()
  val y = out Bool()
  val logic = new Area {
    override def getName(): String = super.getName(); val r = RegNext(a) init(False)
  }
  y := logic.r
}
object Round21Fixtures {
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    def write(name: String)(gen: => Component): Unit = {
      val dir = root.resolve(name); Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory = dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile,
        DbOptions(pdg = false, blocks = false, hgldd = false, sourceRoots = Nil))(gen)
    }
    for (n <- 0 to 1) write(s"area$n")(new Round21Area)
    write("override")(new Round21OverrideArea)
    write("trait")(new Round21TraitArea)
    write("super")(new Round21SuperArea)
  }
}
