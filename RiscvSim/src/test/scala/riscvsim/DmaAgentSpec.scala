package riscvsim
import org.scalatest.funsuite.AnyFunSuite
class DmaAgentSpec extends AnyFunSuite {
  test("noncoherent DMA requires clean before device read and invalidate after device write") {
    val expected = new MemoryImage(64); val backing = new MemoryImage(64)
    val c = new CacheScoreboard(expected, 4, 1, 1)
    c.fill(0, expected.read(0, 4))
    expected.write(0, Vector[Byte](9), 1); c.store(0, Vector[Byte](9), 1)
    val events = scala.collection.mutable.ArrayBuffer.empty[ujson.Obj]
    val dma = new DmaAgent(backing, expected, None, e => { events += e; () })
    intercept[IllegalArgumentException](dma.read(0, 4, false))
    assert(events.isEmpty)
    c.evict(0, Some(expected.read(0, 4))); backing.write(0, Vector[Byte](9), 1)
    assert(dma.read(0, 1, false) == Vector[Byte](9))
    c.fill(0, expected.read(0, 4))
    dma.write(0, Vector[Byte](7), 1, false)
    intercept[IllegalArgumentException](c.read(0, Vector[Byte](9)))
    c.invalidate(0); c.fill(0, backing.read(0, 4)); c.read(0, Vector[Byte](7))
    intercept[IllegalArgumentException](dma.write(0, Vector[Byte](1), 1, true))
    assert(events.size == 2 && events.map(_("id").str).distinct.size == 2)
  }
  test("coherent DMA snoops dirty CPU buffer and invalidates before write") {
    val expected = new MemoryImage(64); val backing = new MemoryImage(64)
    val c = new CacheScoreboard(expected, 4, 1, 1)
    c.fill(0, expected.read(0, 4))
    // Independent CPU atomic stimulus: byte changes from 0 to 1.
    expected.write(0, Vector[Byte](1), 1); c.store(0, Vector[Byte](1), 1)
    var cleaned = false; var invalidated = false
    val snoop = new DmaSnoop {
      def beforeRead(a: Int, n: Int): Unit = {
        c.evict(0, Some(Vector[Byte](1, 0, 0, 0)))
        backing.write(0, Vector[Byte](1), 1); cleaned = true
      }
      def beforeWrite(a: Int, n: Int): Unit = { c.invalidate(0); invalidated = true }
    }
    val dma = new DmaAgent(backing, expected, Some(snoop), _ => ())
    assert(dma.read(0, 1, true) == Vector[Byte](1) && cleaned)
    c.fill(0, backing.read(0, 4))
    dma.write(0, Vector[Byte](5, 6), 2, true)
    assert(invalidated && !c.contains(0))
    c.fill(0, backing.read(0, 4)); c.read(0, Vector[Byte](1, 6))
  }
}
