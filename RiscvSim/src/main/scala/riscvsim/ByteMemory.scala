package riscvsim

/** Dense byte RAM. Missing reads return the caller's value. Writes stay in range. */
final class ByteMemory(base: Long, size: Int) {
  require(base >= 0 && size > 0 && base <= Long.MaxValue - size)
  private val data = new Array[Byte](size)
  /** Same-build harness RAM image. The caller binds base and size in its envelope. */
  def sha256: String = java.security.MessageDigest.getInstance("SHA-256").digest(data).map(b => f"${b & 255}%02x").mkString
  def save(out: java.io.OutputStream): Unit = out.write(data)
  def restore(in: java.io.InputStream): Unit = {
    val image = in.readNBytes(size)
    require(image.length == size && in.read() == -1, "RAM snapshot size mismatch")
    System.arraycopy(image, 0, data, 0, size)
  }
  def getOrElse(address: Long, missing: => Int): Int =
    if (address >= base && address - base < size) data((address - base).toInt) & 255 else missing
  def update(address: Long, value: Int): Unit = {
    require(address >= base && address - base < size, "RAM write outside range")
    data((address - base).toInt) = value.toByte
  }
}
