package examplesocsmp

import spinal.core._
import spinal.core.fiber._
import spinal.lib._
import rvwsoc._
import rvwsmp.SmpTop

/** Optional peripheral host. Shared RAM and AMOs retain the SMP memory ports. */
class SmpHost extends Component with SimpleCoreWrapper {
  val io=new Bundle {
    val bus=master(SimpleCpuBus())
    val interrupts=in Bits(32 bits)
    val debugReset=in Bool()
    val retired=out Vec(UInt(32 bits),2)
    val mmio=out Vec(UInt(32 bits),2)
  }
  def bus=io.bus
  def interrupts=io.interrupts
  def debugReset=io.debugReset
  val area=new ClockingArea(ClockDomain.current.copy(reset=ClockDomain.current.readResetWire || io.debugReset)) {
    val smp=new SmpTop("smp2")
    smp.enables:=3
    val memory=Fiber patch new Area {
      val fetch=Vec(smp.ports.fetch.map(b => master(cloneOf(b))))
      val lsu=Vec(smp.ports.lsu.map(b => master(cloneOf(b))))
      val selected=Reg(UInt(1 bits)) init(0)
      val active=Reg(Bool()) init(False)
      val turn=Reg(UInt(1 bits)) init(0)
      val request=Vec(Bool(),2)
      val pending=Vec(Bool(),2)
      val counts=Vec.fill(2)(Reg(UInt(32 bits)) init(0))
      for(h <- 0 until 2) {
        fetch(h).cmd << smp.ports.fetch(h).cmd
        smp.ports.fetch(h).rsp << fetch(h).rsp
        val up=smp.ports.lsu(h);val down=lsu(h)
        request(h):=up.cmd.address(31 downto 16)===0x1000
        val outstanding=Reg(UInt(log2Up(up.p.pendingMax+1) bits)) init(0)
        when(down.cmd.fire =/= down.rsp.valid) {
          when(down.cmd.fire) { outstanding:=outstanding+1 }.otherwise { outstanding:=outstanding-1 }
        }
        pending(h):=up.cmd.valid && request(h) && outstanding===0
        down.cmd.valid:=up.cmd.valid && !request(h)
        down.cmd.payload:=up.cmd.payload
        up.rsp.valid:=down.rsp.valid
        up.rsp.payload:=down.rsp.payload
        up.cmd.ready := Mux(request(h),active && selected===h && io.bus.ready,down.cmd.ready)
        when(active && selected===h && io.bus.ready) {
          up.rsp.valid := True
          up.rsp.id := up.cmd.id
          up.rsp.data := (io.bus.rdata.resize(64) |<< (up.cmd.address(2).asUInt<<5))
          up.rsp.error := io.bus.error || up.cmd.amoEnable || up.cmd.size>2
          up.rsp.scMiss := False
          counts(h):=counts(h)+1
        }
        smp.ports.software(h):=io.interrupts(3)
        smp.ports.timer(h):=io.interrupts(7)
        smp.ports.external(h):=io.interrupts(11)
        smp.ports.time(h):=0
        val commit=smp.cores(h).rework {
          out(CombInit(smp.cores(h).host[vexiiriscv.misc.PrivilegedPlugin].logic.harts(0).commitMask))
        }
        val exposed=smp.rework { commit.toIo() }
        val retired=Reg(UInt(32 bits)) init(0)
        retired:=retired+CountOne(exposed).resized
        io.retired(h):=retired;io.mmio(h):=counts(h)
      }
      when(!active && pending.asBits.orR) {
        selected:=Mux(pending(turn),turn,~turn)
        active:=True
      }
      when(active && io.bus.ready) { active:=False;turn:= ~selected }
      val cmd=smp.ports.lsu(selected).cmd
      io.bus.valid:=active && !cmd.amoEnable && cmd.size<=2
      io.bus.address:=cmd.address.resized
      io.bus.write:=cmd.write
      io.bus.wdata:=(cmd.data |>> (cmd.address(2).asUInt<<5)).resized
      io.bus.mask:=(cmd.mask |>> (cmd.address(2).asUInt<<2)).resized
      // Invalid peripheral atomics/wide accesses complete with an error and no PSEL.
      when(active && (cmd.amoEnable || cmd.size>2)) {
        for(h <- 0 until 2) when(selected===h) {
          smp.ports.lsu(h).cmd.ready := True
          smp.ports.lsu(h).rsp.valid := True
          smp.ports.lsu(h).rsp.id := cmd.id
          smp.ports.lsu(h).rsp.data := 0
          smp.ports.lsu(h).rsp.error := True
          smp.ports.lsu(h).rsp.scMiss := False
        }
        active:=False;turn:= ~selected
      }
    }
  }
}
