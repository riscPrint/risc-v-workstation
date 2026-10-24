package spinaldb

import java.io.File
import spinal.core._

/** Round-19 port probe from /tmp/review19-design/Port19.scala. A generated-name output
  * register must keep its declaration attributes and unknown-tag marker in diff. */
class Round19Port(initValue: Int, unknownTag: Boolean) extends Component {
  setDefinitionName("Round19Port")
  val a = in Bool()
  val y = out(Reg(Bool()))
  y.setName("_zz_y")
  y := a
  if (unknownTag) y.addTag(new SpinalTag {}) else y.addAttribute("init", initValue)
}

object Round19Fixtures {
  def main(args: Array[String]): Unit = {
    val root = new File(args(0)); root.mkdirs()
    def write(name: String, value: Int, unknown: Boolean): Unit =
      SpinalDB.generate(SpinalConfig(targetDirectory = new File(root, "rtl-" + name).getPath),
        new File(root, name + ".db"), DbOptions(pdg = false, blocks = false, hgldd = false))(
        new Round19Port(value, unknown))
    for (n <- 0 to 1) write(s"r19_port_init$n", n, false)
    write("r19_port_unknown", 0, true)
  }
}
