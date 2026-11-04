package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class SerializedMemorySpec extends AnyFunSuite {
  test("accepted memory order permits either hart first and captures external writes") {
    for (first <- Seq("hart-0:0", "hart-1:0")) {
      val m = new SerializedMemoryReference(Seq.fill[Byte](8)(0))
      m.write(0, "dma-0", 0, Seq[Byte](7,8), Seq[Byte](7,8), 3)
      assert(m.read(1, first, 0, Seq[Byte](7,8)) == Vector("dma-0", "dma-0"))
      val second = if (first.startsWith("hart-0")) "hart-1:0" else "hart-0:0"
      m.write(2, second, 0, Seq[Byte](9,0), Seq[Byte](9,99), 1)
      assert(m.read(3, "read", 0, Seq[Byte](9,8)) == Vector(second, "dma-0"))
    }
  }
  test("wrong data, missing external actions and serialization gaps cannot match") {
    val m = new SerializedMemoryReference(Seq.fill[Byte](8)(0))
    intercept[IllegalArgumentException](m.read(0,"read",0,Seq[Byte](1)))
    intercept[IllegalArgumentException](m.write(1,"gap",0,Seq[Byte](1),Seq[Byte](1),1))
    intercept[IllegalArgumentException](m.write(0,"wrong",0,Seq[Byte](1),Seq[Byte](2),1))
    m.write(0,"write",0,Seq[Byte](1),Seq[Byte](1),1)
    intercept[IllegalArgumentException](m.read(1,"write",0,Seq[Byte](1)))
    assert(m.read(1,"read",0,Seq[Byte](1)) == Vector("write"))
  }
}
