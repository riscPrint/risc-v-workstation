package riscvsim

/**
 * The riscv-tests / ACT `tohost` convention: the program stores 1 for a pass, or
 * `(code << 1) | 1` for a failure. `ToHost` merges the stores a core reports into the
 * 64-bit tohost word and decodes it.
 *
 * Feed it every store the core makes visible (address, log2 size, data as on the bus:
 * narrow stores may be replicated across the word, so the byte lanes are taken from the
 * address offset).
 */
class ToHost(val address: Long) {
  private var word = BigInt(0)

  /** Returns the decoded result once the word becomes non-zero. */
  def onStore(addr: BigInt, sizeLog2: Int, data: BigInt): Option[ToHost.Result] = {
    if (addr < address || addr >= address + 8) return None
    val off = (addr - address).toInt
    val bytes = 1 << sizeLog2
    for (b <- off until (off + bytes min 8)) {
      val byte = (data >> (8 * b)) & 0xff
      word = (word & ~(BigInt(0xff) << (8 * b))) | (byte << (8 * b))
    }
    if (word == 0) None else Some(ToHost.decode(word))
  }

  def value: BigInt = word
}

object ToHost {
  sealed trait Result
  case object Pass extends Result
  /** `code` is the value >> 1. `odd` is false for even values (proxy-kernel syscalls, unsupported). */
  case class Fail(code: Long, raw: BigInt, odd: Boolean) extends Result

  def decode(v: BigInt): Result =
    if (v == 1) Pass else Fail((v >> 1).toLong, v, v.testBit(0))

  /** The `tohost` symbol of an ELF, if present. */
  def find(elf: ElfFile): Option[Long] = elf.symbol("tohost")
}

/**
 * Follows `count` 64-bit little-endian words at `base` through the stores a core reports
 * (same byte-lane merge as ToHost). Used for `bench_stats` (ROI cycles, instret).
 */
class MemWords(val base: Long, val count: Int) {
  val words: Array[BigInt] = Array.fill(count)(BigInt(0))
  /** Bit i of masks(w) is set once byte i of word w was written. */
  val masks: Array[Int] = Array.fill(count)(0)

  def onStore(addr: BigInt, sizeLog2: Int, data: BigInt): Unit =
    for (a <- addr until addr + (1 << sizeLog2) if a >= base && a < base + 8 * count) {
      val w = ((a - base) / 8).toInt
      val lane = (a & 7).toInt
      val byte = (data >> (8 * lane)) & 0xff
      words(w) = (words(w) & ~(BigInt(0xff) << (8 * lane))) | (byte << (8 * lane))
      masks(w) |= 1 << lane
    }

  def complete: Boolean = masks.forall(_ == 0xff)
  def touched: Boolean = masks.exists(_ != 0)
}
