package riscvsim
import org.scalatest.funsuite.AnyFunSuite

class CacheScoreboardSpec extends AnyFunSuite {
  test("hit, miss, same-set alias, byte writes, eviction and writeback") {
    val mem = new MemoryImage(128)
    mem.write(0, Vector[Byte](1, 2, 3, 4), 15)
    val c = new CacheScoreboard(mem, 4, 2, 1)
    intercept[IllegalArgumentException](c.read(0, Vector[Byte](1)))
    c.fill(0, mem.read(0, 4)); c.read(0, Vector[Byte](1, 2))
    c.fill(4, mem.read(4, 4))
    intercept[IllegalArgumentException](c.fill(8, mem.read(8, 4)))
    mem.write(1, Vector[Byte](9, 8), 1)
    intercept[IllegalArgumentException](c.store(1, Vector[Byte](7, 8), 1))
    c.store(1, Vector[Byte](9, 8), 1); c.read(0, Vector[Byte](1, 9, 3, 4))
    intercept[IllegalArgumentException](c.evict(0, None))
    intercept[IllegalArgumentException](c.evict(0, Some(Vector[Byte](0, 0, 0, 0))))
    c.evict(0, Some(mem.read(0, 4))); c.fill(8, mem.read(8, 4))
    assert(!c.contains(0) && c.contains(8) && c.contains(4))
  }
  test("denied fills do not install; wrong data and invalid bounds fail") {
    val mem = new MemoryImage(16); val c = new CacheScoreboard(mem, 4, 1, 1)
    c.fill(0, Vector.fill[Byte](4)(0), denied = true)
    assert(!c.contains(0))
    intercept[IllegalArgumentException](c.fill(0, Vector.fill[Byte](4)(1)))
    intercept[IllegalArgumentException](mem.write(15, Vector[Byte](1, 2), 3))
    intercept[IllegalArgumentException](mem.write(0, Vector[Byte](1), 2))
  }
  test("self-modifying code needs observed instruction invalidation and refill") {
    val mem = new MemoryImage(16)
    mem.write(0, Vector[Byte](0x13, 0, 0, 0), 15)
    val i = new CacheScoreboard(mem, 4, 1, 1)
    val d = new CacheScoreboard(mem, 4, 1, 1)
    i.fill(0, mem.read(0, 4)); d.fill(0, mem.read(0, 4))
    mem.write(0, Vector[Byte](0x73), 1)
    d.store(0, Vector[Byte](0x73), 1)
    intercept[IllegalArgumentException](i.read(0, Vector[Byte](0x13)))
    d.evict(0, Some(mem.read(0, 4)))
    i.invalidate(0); i.fill(0, mem.read(0, 4)); i.read(0, Vector[Byte](0x73))
  }
}
