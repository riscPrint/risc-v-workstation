package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._

/** Volatile eight-sector block device. Each sector has 128 little-endian words.
  * Commands select a sector transfer; exactly 128 DATA accesses complete it.
  * This is a verification block store, not an SD card protocol implementation.
  */
class BlockDevice extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32)))
    val irq = out Bool()
  }
  val lba = Reg(UInt(32 bits)) init(0)
  val index = Reg(UInt(7 bits)) init(0)
  val active = Reg(Bool()) init(False)
  val writing = Reg(Bool()) init(False)
  val error = Reg(Bool()) init(False)
  val done = Reg(Bool()) init(False)
  val storage = Mem(Bits(32 bits),1024)
  storage.initBigInt(Seq.fill(1024)(BigInt(0)))
  val address = (lba(2 downto 0) ## index).asUInt
  val access = io.bus.PSEL.lsb && io.bus.PENABLE
  val read = access && !io.bus.PWRITE
  val write = access && io.bus.PWRITE
  val dataAccess = access && io.bus.PADDR === 16
  val dataValid = active && (io.bus.PWRITE === writing)
  io.bus.PREADY := True
  io.bus.PSLVERROR := io.bus.PADDR(1 downto 0) =/= 0 ||
    (dataAccess && !dataValid) || (access && io.bus.PADDR > 20)
  io.bus.PRDATA := 0
  io.irq := done || error
  when(dataAccess && dataValid) {
    when(index === 127) { active := False; done := True }
      .otherwise { index := index + 1 }
  }
  when(dataAccess && dataValid && writing) { storage.write(address,io.bus.PWDATA) }
  switch(io.bus.PADDR) {
    is(0) {
      io.bus.PRDATA := lba.asBits
      when(write && !active) { lba := io.bus.PWDATA.asUInt }
      when(write && active) { io.bus.PSLVERROR := True }
    }
    is(4) {
      when(read) { io.bus.PSLVERROR := True }
      // Command 0 aborts. Commands 1/2 start read/write transfers.
      when(write) {
        when(io.bus.PWDATA === 0) { active := False }
          .elsewhen(active || lba >= 8 || (io.bus.PWDATA =/= 1 && io.bus.PWDATA =/= 2)) {
            error := True
            io.bus.PSLVERROR := True
          }.otherwise {
            index := 0; active := True; writing := io.bus.PWDATA === 2
            done := False; error := False
          }
      }
    }
    is(8) {
      io.bus.PRDATA(0) := active; io.bus.PRDATA(1) := error; io.bus.PRDATA(2) := done
      when(write) {
        when(io.bus.PWDATA(1)) { error := False }
        when(io.bus.PWDATA(2)) { done := False }
      }
    }
    is(12) { io.bus.PRDATA := B(8,32 bits); when(write) { io.bus.PSLVERROR := True } }
    is(16) { io.bus.PRDATA := storage.readAsync(address) }
    is(20) { io.bus.PRDATA := index.asBits.resized; when(write) { io.bus.PSLVERROR := True } }
  }
}
