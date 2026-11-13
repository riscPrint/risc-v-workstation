package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class CacheEventObserverSpec extends AnyFunSuite {
  val names = Seq("fill", "read", "store", "denied", "publish", "sync", "fetch_request", "fetch_reply", "fetch_consume", "fetch_discard")
  def event(kind: String, hart: Int = 0) = ujson.Obj("event" -> kind, "hart" -> hart,
    "cycle" -> 0, "physical_address" -> "0x0", "id" -> "patch", "bytes" -> "01020304")
  test("cross-hart publication checks bytes from a pending fetch only after synchronization") {
    val memory = new MemoryImage(16)
    memory.write(0, Seq[Byte](1, 2, 3, 4), 15)
    val o = new CacheEventObserver(memory, Set(0, 1), 4, 1, 1, names.map(n => n -> n).toMap)
    o.accept(event("publish"))
    val request = event("fetch_request", 1); request("id") = "fetch"; request("publication") = "patch"
    o.accept(request)
    val reply = event("fetch_reply", 1); reply("id") = "fetch"; o.accept(reply)
    val consume = event("fetch_consume", 1); consume("id") = "fetch"
    intercept[IllegalArgumentException](o.accept(consume))
    val sync = event("sync", 1); sync("data_visible") = true; sync("fence_i_complete") = true
    o.accept(sync); o.accept(consume)
    o.finish(Set("fetch_consume", "sync"), Set(1 -> "patch"))
  }
  test("declared physical aliases use one byte oracle and corrupt stores fail") {
    val memory = new MemoryImage(16)
    memory.write(0, Seq[Byte](1, 2, 3, 4), 15)
    val o = new CacheEventObserver(memory, Set(0), 4, 1, 1, names.map(n => n -> n).toMap)
    val fill = event("fill"); fill("virtual_address") = "0x1000"; o.accept(fill)
    val read = event("read"); read("virtual_address") = "0x2000"; o.accept(read)
    assert(o.coverage("alias") > 0)
    memory.write(0, Seq[Byte](9), 1)
    val store = event("store"); store("bytes") = "08"; store("mask") = "0x1"
    intercept[IllegalArgumentException](o.accept(store))
    store("bytes") = "09"; o.accept(store)
    o.finish(Set("alias", "store"), Set.empty)
  }
  test("stale fetch replies and absent campaign evidence fail") {
    val memory = new MemoryImage(16)
    memory.write(0, Seq[Byte](1, 2, 3, 4), 15)
    val o = new CacheEventObserver(memory, Set(0), 4, 1, 1, names.map(n => n -> n).toMap)
    o.accept(event("publish"))
    val sync = event("sync"); sync("data_visible") = true; sync("fence_i_complete") = true; o.accept(sync)
    val request = event("fetch_request"); request("id") = "fetch"; request("publication") = "patch"; o.accept(request)
    val reply = event("fetch_reply"); reply("id") = "fetch"; reply("bytes") = "00000000"; o.accept(reply)
    val consume = event("fetch_consume"); consume("id") = "fetch"
    intercept[IllegalArgumentException](o.accept(consume))
    intercept[IllegalArgumentException](o.finish(Set("denied"), Set(0 -> "patch")))
  }
}
