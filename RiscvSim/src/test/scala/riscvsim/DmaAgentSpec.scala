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

class DmaTransportSpec extends org.scalatest.funsuite.AnyFunSuite {
  test("read expectation uses the captured serialization point after a concurrent CPU update") {
    val expected = new MemoryImage(16); val backing = new MemoryImage(16)
    val transport = new DmaTransport {
      def read(a: Int, n: Int, coherent: Boolean, accepted: () => Unit): Vector[Byte] = {
        // Independent CPU AMOADD stimulus wins arbitration before the DMA read.
        expected.write(a,Vector[Byte](1),1)
        accepted(); Vector[Byte](1)
      }
      def write(a: Int, d: Seq[Byte], m: BigInt, coherent: Boolean, accepted: () => Unit): Unit = accepted()
    }
    val dma = new DmaAgent(backing,expected,None,_ => (),Some(transport))
    assert(dma.read(0,1,false) == Vector[Byte](1))
  }
  test("transport must acknowledge exactly once and failed reads do not get capture events") {
    for (mode <- Seq("missing","duplicate","stale")) {
      val expected = new MemoryImage(16); val backing = new MemoryImage(16)
      expected.write(0,Vector[Byte](7),1)
      var captured = 0
      val t = new DmaTransport {
        def read(a: Int,n: Int,c: Boolean,accepted: () => Unit): Vector[Byte] = {
          if (mode != "missing") accepted()
          if (mode == "duplicate") accepted()
          Vector[Byte](0)
        }
        def write(a: Int,d: Seq[Byte],m: BigInt,c: Boolean,accepted: () => Unit): Unit = ()
      }
      val dma = new DmaAgent(backing,expected,None,_ => captured += 1,Some(t))
      intercept[IllegalArgumentException](dma.read(0,1,false))
      assert(captured == 0)
      intercept[IllegalArgumentException](dma.write(0,Vector[Byte](9),1,false))
      assert(expected.read(0,1) == Vector[Byte](7) && captured == 0)
    }
  }
}
