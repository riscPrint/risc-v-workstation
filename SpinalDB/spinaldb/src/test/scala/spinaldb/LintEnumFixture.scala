package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

class HashedEnumReference extends Component {
  object StateDef extends SpinalEnum { val idle, run, lost = newElement() }
  StateDef.setName("LongStateDefinition" * 40)
  val enable = in Bool()
  val result = out Bits(2 bits)
  val stateReg = Reg(StateDef()) init(StateDef.idle)
  when(enable) { stateReg := StateDef.run }.otherwise { stateReg := StateDef.idle }
  result := stateReg.asBits
}
object LintEnumFixture {
  def main(args: Array[String]): Unit = {
    val dir = Paths.get(args(0)); Files.createDirectories(dir)
    SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
      dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false))(
      new HashedEnumReference)
  }
}
