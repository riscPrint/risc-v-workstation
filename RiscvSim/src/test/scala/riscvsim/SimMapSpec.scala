package riscvsim
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
class SimMapSpec extends AnyFunSuite {
  def load(regions: String): SimMap = {
    val f = Files.createTempFile("sim-map", ".json")
    try {
      Files.writeString(f, s"""{"schema":"rvw.sim-map/1","address_bits":32,"regions":$regions,"interrupts":[]}""")
      SimMap.load(f.toFile)
    } finally Files.delete(f)
  }
  val ram = """{"name":"ram","kind":"ram","base":"0x80000000","size":"0x1000","permissions":"rx","cacheable":false,"registers":[]}"""
  test("runtime region bounds and permissions use the captured map") {
    val m = load(s"[$ram]")
    assert(m.region(BigInt("80000000",16), 4, 'x').isDefined)
    assert(m.region(BigInt("80000ffc",16), 8, 'r').isEmpty)
    assert(m.region(BigInt("80000000",16), 4, 'w').isEmpty)
    assert(m.region(BigInt("80001000",16), 1, 'r').isEmpty)
    assert(m.sha256.length == 64)
  }
  test("overlapping and nonaligned windows are refused") {
    intercept[IllegalArgumentException](load(s"[$ram,$ram]"))
    intercept[IllegalArgumentException](load(s"[${ram.replace("0x1000", "0x1001")}]"))
  }
  test("64-bit reset values remain exact and unsupported widths are refused") {
    val mmio = """{"name":"timer","kind":"mmio","base":"0x02000000","size":"0x1000","permissions":"rw","cacheable":false,"registers":[{"name":"compare","offset":0,"width":64,"access":"rw","reset":"0xffffffffffffffff","read_action":"none","write_action":"normal"}]}"""
    assert(load(s"[$mmio]").reset("timer", "compare") == -1L)
    intercept[IllegalArgumentException](load(s"[${mmio.replace("\"width\":64", "\"width\":4294967360")}]"))
  }
}
