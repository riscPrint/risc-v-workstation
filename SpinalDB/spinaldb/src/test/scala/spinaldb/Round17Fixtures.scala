package spinaldb

import java.io.File
import spinal.core._

class Round17PlainArea extends Area { val x = Bool() }
class Round17HiddenArea extends Area { override def getName(): String = "hidden" }

class Round17ResetBool(mode: Int) extends Bool {
  override def hasInit: Boolean = super.hasInit && mode == 0
}
class Round17Reset(mode: Int, generated: Boolean = false) extends Component {
  setDefinitionName("Round17Reset")
  val a = in Bool()
  val y = out Bool()
  val r = new Round17ResetBool(mode)
  r.setAsReg(); r.init(False); r := a
  if (generated) r.setName("_zz_custom")
  y := r
}
class Round17HiddenBundle extends Bundle {
  val q = Bool()
  override def getBitsWidth: Int = super.getBitsWidth
}
class Round17Unused(container: Boolean) extends Component {
  val a = in Bool()
  val y = out Bool()
  y := a
  def hidden(): Unit = {
    val r = if (container) new Round17HiddenBundle().q else new Round17ResetBool(0)
    r.setAsReg(); r.init(False); r := a; r.setName("_zz_unused"); r.dontSimplifyIt()
  }
  hidden()
}

object Round17Fixtures {
  def main(args: Array[String]): Unit = {
    val root = new File(args(0)); root.mkdirs()
    def write(name: String)(gen: => Component): Unit =
      SpinalDB.generate(SpinalConfig(targetDirectory = new File(root, "rtl-" + name).getPath),
        new File(root, name + ".db"), DbOptions(pdg = false, blocks = false, hgldd = false))(gen)
    for (mode <- 0 to 1; generated <- Seq(false, true))
      write(s"r17_reset${mode}_${if (generated) "gen" else "named"}")(new Round17Reset(mode, generated))
    write("r17_clockbox")(new Round17BoxTop)
    for (container <- Seq(false, true))
      write(s"r17_unused${if (container) 1 else 0}")(new Round17Unused(container))
  }
}
