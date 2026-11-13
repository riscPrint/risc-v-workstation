package riscvsim

/** Dense byte RAM. Missing reads return the caller's value. Writes stay in range. */
final class ByteMemory(base: Long, size: Int) {
  require(base >= 0 && size > 0 && base <= Long.MaxValue - size)
  private val data = new Array[Byte](size)
  def getOrElse(address: Long, missing: => Int): Int =
    if (address >= base && address - base < size) data((address - base).toInt) & 255 else missing
  def update(address: Long, value: Int): Unit = {
    require(address >= base && address - base < size, "RAM write outside range")
    data((address - base).toInt) = value.toByte
  }
}
