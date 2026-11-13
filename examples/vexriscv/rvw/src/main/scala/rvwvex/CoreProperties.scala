package rvwvex

import spinal.core._
import spinalchecks.Sva
import java.nio.file.{Files, Paths}
import scala.collection.mutable.ArrayBuffer

/** Project-owned property bindings. No upstream source edits are needed. */
object CoreProperties {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "CoreProperties OUTPUT_DIRECTORY")
    val directory = Paths.get(args(0))
    Files.createDirectories(directory)
    val statements = ArrayBuffer.empty[String]
    val report = VexTop.spinalConfig.copy(targetDirectory = args(0)).generateVerilog {
      val top = new VexTop
      top.rework {
        import Sva._
        val clock = signal("clk")
        val reset = Some(signal("reset"))
        def observe(name: String, value: BaseType): Expr = {
          val port = out(cloneOf(value)).setName("property_" + name)
          port.assignFromBits(value.asBits)
          signal(port)
        }
        def check(name: String, when: Expr, expect: Expr, next: Boolean = false): Unit =
          statements += when.sequence.implies(expect.sequence, overlap = !next).assertOn(name, clock, reset)
        val stages = top.stages.toSeq
        val pcs = stages.zipWithIndex.map { case (stage, index) =>
          val prefix = "stage" + index
          val a = stage.arbitration
          val valid = observe(prefix + "_valid", a.isValid)
          val stuck = observe(prefix + "_stuck", a.isStuck)
          val fire = observe(prefix + "_fire", a.isFiring)
          val removed = observe(prefix + "_removed", a.removeIt)
          val flush = observe(prefix + "_flush", a.isFlushed)
          val pc = observe(prefix + "_pc", stage.input(top.PC))
          check(prefix + "_fire_valid", fire, valid)
          check(prefix + "_fire_not_stuck", fire, !stuck)
          check(prefix + "_fire_not_removed", fire, !removed)
          check(prefix + "_stall_pc", valid && stuck && !removed && !flush, pc.equal(pc.past), next = true)
          (pc, fire)
        }
        for (i <- 0 until pcs.size - 1)
          check("pc_chain_" + i, pcs(i)._2, pcs(i + 1)._1.equal(pcs(i)._1.past), next = true)
        val iv = observe("ibus_valid", top.ibus.cmd.valid)
        val ir = observe("ibus_ready", top.ibus.cmd.ready)
        val ip = observe("ibus_pc", top.ibus.cmd.pc)
        check("ibus_hold_valid", iv && !ir, iv, next = true)
        check("ibus_hold_pc", iv && !ir, ip.equal(ip.past), next = true)
        check("ibus_pc_aligned", iv, observe("ibus_aligned", top.ibus.cmd.pc(1 downto 0) === 0))
        val dv = observe("dbus_valid", top.dbus.cmd.valid)
        val dr = observe("dbus_ready", top.dbus.cmd.ready)
        val da = observe("dbus_address", top.dbus.cmd.address)
        val dd = observe("dbus_data", top.dbus.cmd.data)
        val dw = observe("dbus_write", top.dbus.cmd.wr)
        val ds = observe("dbus_size", top.dbus.cmd.size)
        check("dbus_hold_valid", dv && !dr, dv, next = true)
        check("dbus_hold_address", dv && !dr, da.equal(da.past), next = true)
        check("dbus_hold_data", dv && !dr && dw, dd.equal(dd.past), next = true)
        check("dbus_hold_write", dv && !dr, dw.equal(dw.past), next = true)
        check("dbus_hold_size", dv && !dr, ds.equal(ds.past), next = true)
        val rv = observe("retire", top.rvfi.valid)
        val rd = observe("rd", top.rvfi.rd.addr)
        val wd = observe("rd_data", top.rvfi.rd.wdata)
        check("x0_write_zero", rv && rd.equal(BigInt(0)), wd.equal(BigInt(0)))
        check("retire_machine", rv, observe("machine", top.rvfi.mode === B(3, 2 bits)))
        check("retire_rv32", rv, observe("rv32", top.rvfi.ixl === B(1, 2 bits)))
        check("retire_pc_aligned", rv, observe("retire_aligned", top.rvfi.pc.rdata(1 downto 0) === 0))
        val trap = observe("trap", top.traps.valid)
        def csr(address: Int): Bits = {
          val value = Bits(32 bits).allowOverride
          value := 0
          for (r <- top.csr.csrMapping.mapping(address).collect { case r: vexriscv.plugin.CsrRead => r })
            value(r.bitOffset, r.that.getBitsWidth bits) := r.that.asBits
          value
        }
        check("trap_mie_clear", trap, !observe("mie", csr(0x300)(3)))
        check("trap_mpp_machine", trap, observe("mpp_machine", csr(0x300)(12 downto 11) === B(3, 2 bits)))
        check("trap_mepc_aligned", trap, observe("mepc_aligned", csr(0x341)(1 downto 0) === 0))
        statements += rv.sequence.property.coverOn("retirement_reached", clock, reset)
        statements += trap.sequence.property.coverOn("trap_reached", clock, reset)
      }
      top
    }
    Sva.write(directory.resolve("properties.sv"), statements.toSeq)
    println(s"CORE_PROPERTIES ${statements.size} ${report.generatedSourcesPaths.mkString(",")}")
  }
}
