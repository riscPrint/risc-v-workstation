package riscvsim

/** A project transport waits for the accepted transaction at its serialization
  * boundary. It calls accepted exactly once at that boundary, before advancing
  * simulation. A read returns the bytes sampled at that boundary. */
trait DmaTransport {
  def supportsCoherence: Boolean = false
  def read(address: Int, count: Int, coherent: Boolean, accepted: () => Unit): Vector[Byte]
  def write(address: Int, data: Seq[Byte], mask: BigInt, coherent: Boolean, accepted: () => Unit): Unit
}
