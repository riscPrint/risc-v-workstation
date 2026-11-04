package riscvsim
import org.scalatest.funsuite.AnyFunSuite
class InstructionVisibilitySpec extends AnyFunSuite {
  test("cross-hart publication needs data visibility and reader local fence") {
    val expected = new MemoryImage(128)
    val bytes = Vector[Byte](0x93.toByte, 5, 0x70, 0)
    expected.write(60, bytes, 15)
    val m = new InstructionVisibility(expected, Set(0,1))
    m.publish("patch", 60, bytes)
    intercept[IllegalArgumentException](m.synchronize(1,"patch",false,true))
    intercept[IllegalArgumentException](m.synchronize(1,"patch",true,false))
    intercept[IllegalArgumentException](m.fetch(1,"patch",60,bytes))
    m.synchronize(0,"patch",true,true)
    intercept[IllegalArgumentException](m.fetch(1,"patch",60,bytes))
    m.synchronize(1,"patch",true,true)
    intercept[IllegalArgumentException](m.fetch(1,"patch",60,Vector[Byte](0x93.toByte,5,0x10,0)))
    intercept[IllegalArgumentException](m.finish(Set(1 -> "patch")))
    m.fetch(1,"patch",60,bytes); m.finish(Set(1 -> "patch"))
  }
  test("new publications cannot reuse an older synchronization or observation") {
    val expected = new MemoryImage(128)
    val m = new InstructionVisibility(expected, Set(0))
    for (n <- 1 to 2) {
      val bytes = Vector[Byte](n.toByte,0,0,0)
      expected.write(124,bytes,15); m.publish(s"p$n",124,bytes)
      intercept[IllegalArgumentException](m.fetch(0,s"p$n",124,bytes))
      m.synchronize(0,s"p$n",true,true); m.fetch(0,s"p$n",124,bytes)
    }
    intercept[IllegalArgumentException](m.fetch(0,"p1",124,Vector[Byte](1,0,0,0)))
    intercept[IllegalArgumentException](m.synchronize(0,"p1",true,true))
    m.finish(Set(0 -> "p1",0 -> "p2"))
    intercept[IllegalArgumentException](m.publish("p2",124,Vector[Byte](2,0,0,0)))
  }
}
