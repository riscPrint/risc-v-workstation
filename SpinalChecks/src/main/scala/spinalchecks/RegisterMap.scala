package spinalchecks

import java.io.{FileInputStream, File}
import java.util.Properties

case class MappedRegister(name: String, address: BigInt, model: RegisterModel) {
  def csr(minPrivilege: Int, allowed: Seq[BigInt] = Nil, wlrl: Boolean = false,
          legalize: Map[BigInt, BigInt] = Map.empty): CsrModel =
    CsrModel(1, model.width, model.reset, model.writeMask, minPrivilege, allowed,
      model.w1cMask, model.readClearMask, legalize, wlrl,
      readOnly = (model.writeMask | model.w1cMask) == 0)
}
object RegisterMap {
  /** Input is the strict normalized output of scripts/import-map.py. */
  def load(file: File): Seq[MappedRegister] = {
    val p = new Properties
    val in = new FileInputStream(file)
    try p.load(in) finally in.close()
    def get(k: String): String = Option(p.getProperty(k)).getOrElse(
      throw new IllegalArgumentException(s"missing map property $k"))
    require(get("version") == "1")
    val names = get("registers").split(",").toSeq
    require(names.nonEmpty && names.distinct.size == names.size)
    val result = names.map { n =>
      require(n.matches("[A-Za-z_][A-Za-z0-9_.]*"))
      def number(k: String): BigInt = BigInt(get(s"$n.$k"))
      val width = number("width")
      require(width.isValidInt && width > 0, "register width must be a positive Int")
      MappedRegister(n, number("address"), RegisterModel(1, width.toInt,
        number("reset"), number("writeMask"), number("w1cMask"), number("readClearMask")))
    }
    require(result.forall(_.address >= 0))
    val spans = result.map(r => (r.address, r.address + (BigInt(r.model.width) + 7) / 8)).sortBy(_._1)
    require(spans.sliding(2).forall(x => x.size < 2 || x.head._2 <= x.last._1), "overlapping registers")
    result
  }
}
