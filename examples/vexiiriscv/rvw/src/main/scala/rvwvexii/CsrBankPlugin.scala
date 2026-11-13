package rvwvexii

import spinal.core._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.execute.CsrAccessPlugin
import vexiiriscv.misc.PipelineBuilderPlugin
import spinalchecks.DeclaredChecks

/** Independent software readback through the accepted CSR interface.
  * RAM storage needs no register-name guess. Trap updates invalidate affected
  * banks. This does not check denied accesses or independently model traps.
  */
class CsrBankPlugin(model: ujson.Value, observationFault: Boolean = false) extends FiberPlugin {
  val logic = during setup new Area {
    val buildBefore = retains(host[PipelineBuilderPlugin].elaborationLock)
    awaitBuild()
    require(model("banks").arr.map(_("name").str).distinct.size == model("banks").arr.size)
    require(model("views").arr.size == model("banks").arr.size &&
      model("views").arr.map(_("bank").str).distinct.size == model("views").arr.size,
      "this project binding requires one unaliased view per bank")
    val bus = host[CsrAccessPlugin].bus.get
    val trap = host[TrapTapPlugin].logic.fire
    val banks = model("banks").arr.map { b =>
      require(b("width").num == 32, "this project binds RV32 storage only")
      b("name").str -> (Reg(Bits(32 bits)).init(BigInt(b("reset").num.toLong)), RegInit(True))
    }.toMap
    for (view <- model("views").arr if view.obj.get("present").forall(_.bool)) {
      val name = view("name").str
      require(view("privilege").str == "M" && view.obj.get("shift").forall(_.num == 0), "machine unshifted views only")
      val (expected, known) = banks(view("bank").str)
      val address = view("address").num.toInt
      val mask = B(BigInt(view("mask").num.toLong),32 bits)
      val writeMask = B(BigInt(view("write_mask").num.toLong),32 bits)
      val read = bus.read.valid && bus.read.moving && bus.read.address === address
      val write = bus.write.valid && bus.write.moving && bus.write.address === address
      val observed = if (observationFault && name == "mscratch") bus.read.data ^ B(1,32 bits) else bus.read.data
      DeclaredChecks.rule("csr.read", name, "catalog static-bank accepted readback; RAM supported; mepc/mtval unknown after trap")(
        read && known && observed =/= (expected & mask))
      if (!view.obj.get("read_only").exists(_.bool)) when(write) {
        expected := (expected & ~writeMask) | (bus.write.bits & writeMask)
        known := True
      }
      if (Set("mepc", "mtval")(name)) when(trap) { known := False }
    }
    buildBefore.release()
  }
}
