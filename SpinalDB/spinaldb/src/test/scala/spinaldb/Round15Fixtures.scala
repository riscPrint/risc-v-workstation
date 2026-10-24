package spinaldb

import java.io.File
import spinal.core._

class Round15Liar(n: Int) extends java.math.BigInteger(n.toString) {
  override def toString(radix: Int): String = "0"
}

class Round15Design(kind: String, mode: Int) extends Component {
  setDefinitionName("Round15")
  def number(n: Int): BigInt = new BigInt(new Round15Liar(n))
  if (kind == "analog") {
    val y = inout(Analog(Bool()))
    if (mode == 1) y := True
  } else {
    val a = in Bool()
    val y = out Bits(4 bits)
    kind match {
      case "literal" => y := B(number(mode + 1), 4 bits)
      case "mask" => SpinalDBTestHooks.assignPoisonedBig(y, BigInt(0), number(mode + 1))
      case "meminit" =>
        val mem = Mem(Bits(4 bits), 2)
        mem.initBigInt(Seq(number(mode + 1), BigInt(0)))
        y := mem.readAsync(a.asUInt)
      case "poison" => y.assignDontCare()
    }
  }
}

/** The config pair cannot use Main's default SpinalConfig. Generate all round-15 fixtures together. */
object Round15Fixtures {
  def main(args: Array[String]): Unit = {
    val root = new File(args(0))
    for (kind <- Seq("analog", "literal", "mask", "meminit", "poison"); mode <- 0 to 1) {
      val name = s"r15_${kind}$mode"
      SpinalDB.generate(SpinalConfig(targetDirectory = new File(root, "rtl-" + name).getPath,
        dontCareGenAsZero = kind == "poison" && mode == 1), new File(root, name + ".db"),
        DbOptions(pdg = false, blocks = false, hgldd = false))(new Round15Design(kind, mode))
    }
  }
}
