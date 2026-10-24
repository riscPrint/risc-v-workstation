package riscvsim

/** Lowercase "0x…" hex strings, the format every rvw JSON file uses for wide values. */
object Hex {
  def apply(v: BigInt): String = "0x" + v.toString(16)
  def apply(v: Long): String = "0x" + java.lang.Long.toHexString(v)
  def parse(s: String): BigInt = {
    val t = s.trim.toLowerCase
    if (t.startsWith("0x")) BigInt(t.drop(2), 16) else BigInt(t)
  }
}

object RvwJson {
  /** ujson writes Scala Longs as strings; numbers in rvw files are JSON numbers. */
  def num(v: Long): ujson.Num = ujson.Num(v.toDouble)
}
