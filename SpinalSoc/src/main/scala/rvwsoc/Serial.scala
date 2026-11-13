package rvwsoc
import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.com.uart._
import spinal.lib.com.spi._
import spinal.lib.com.i2c._

/** 16550 register subset with reg-shift=2, 8N1 and one RX/TX holding slot.
  * No modem signals, FIFO trigger levels, DMA or break/parity support.
  */
class Uart16550 extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32)))
    val serial = master(Uart())
    val irq = out Bool()
  }
  val uart = new UartCtrl(UartCtrlGenerics(clockDividerWidth=16))
  io.serial <> uart.io.uart
  val lcr = Reg(Bits(8 bits)) init(3)
  val ier = Reg(Bits(8 bits)) init(0)
  val divisor = Reg(UInt(16 bits)) init(1)
  val scratch = Reg(Bits(8 bits)) init(0)
  uart.io.config.clockDivider := ((divisor << 1) - 1).resized
  uart.io.config.frame.dataLength := 7
  uart.io.config.frame.parity := UartParityType.NONE
  uart.io.config.frame.stop := UartStopType.ONE
  uart.io.writeBreak := False
  val rx = uart.io.read.queue(1)
  val tx = Stream(Bits(8 bits))
  uart.io.write << tx.queue(1)
  val access = io.bus.PSEL.lsb && io.bus.PENABLE
  val read = access && !io.bus.PWRITE
  val write = access && io.bus.PWRITE
  tx.valid := write && io.bus.PADDR === 0 && !lcr(7)
  tx.payload := io.bus.PWDATA(7 downto 0)
  rx.ready := read && io.bus.PADDR === 0 && !lcr(7)
  io.bus.PREADY := True
  when(tx.valid) { io.bus.PREADY := tx.ready }
  io.bus.PSLVERROR := io.bus.PADDR(1 downto 0) =/= 0
  io.bus.PRDATA := 0
  val rxIrq = ier(0) && rx.valid
  val txIrq = ier(1) && tx.ready
  io.irq := rxIrq || txIrq
  switch(io.bus.PADDR) {
    is(0) {
      io.bus.PRDATA := Mux(lcr(7), divisor(7 downto 0).asBits, rx.payload).resized
      when(write && lcr(7)) { divisor(7 downto 0) := io.bus.PWDATA(7 downto 0).asUInt }
    }
    is(4) {
      io.bus.PRDATA := Mux(lcr(7), divisor(15 downto 8).asBits, ier).resized
      when(write) {
        when(lcr(7)) { divisor(15 downto 8) := io.bus.PWDATA(7 downto 0).asUInt }
          .otherwise { ier := io.bus.PWDATA(7 downto 0) }
      }
    }
    is(8) { io.bus.PRDATA := Mux(rxIrq, B(4,32 bits), Mux(txIrq, B(2,32 bits), B(1,32 bits))) }
    is(12) {
      io.bus.PRDATA := lcr.resized
      when(write) { lcr := io.bus.PWDATA(7 downto 0) }
    }
    is(20) {
      io.bus.PRDATA(0) := rx.valid
      io.bus.PRDATA(5) := tx.ready
      // THRE is known. TEMT cannot be inferred from the holding queue alone.
      io.bus.PRDATA(6) := False
    }
    is(28) {
      io.bus.PRDATA := scratch.resized
      when(write) { scratch := io.bus.PWDATA(7 downto 0) }
    }
  }
}

class Spi extends Component {
  val impl = Apb3SpiMasterCtrl(SpiMasterCtrlMemoryMappedConfig(SpiMasterCtrlGenerics(1,16),4,4))
  val io = new Bundle {
    val bus = slave(Apb3(Apb3SpiMasterCtrl.getApb3Config))
    val pins = master(SpiMaster(1))
    val irq = out Bool()
  }
  impl.io.apb <> io.bus
  io.pins <> impl.io.spi
  io.irq := impl.io.interrupt
}

class I2c extends Component {
  val impl = Apb3I2cCtrl(I2cSlaveMemoryMappedGenerics(I2cSlaveGenerics(), 0, I2cMasterMemoryMappedGenerics(12)))
  val io = new Bundle {
    val bus = slave(Apb3(Apb3I2cCtrl.getApb3Config))
    val pins = master(I2c())
    val irq = out Bool()
  }
  impl.io.apb <> io.bus
  io.pins <> impl.io.i2c
  io.irq := impl.io.interrupt
}

object PeripheralElaborate extends App {
  val dest = args.headOption.getOrElse("rtl/peripherals")
  Seq[() => Component](() => new Clint, () => new Plic, () => new Gpio,
    () => new Timer, () => new Finisher, () => new Uart16550, () => new Spi, () => new I2c).foreach { make =>
    SpinalConfig(targetDirectory=dest).generateVerilog(make())
  }
}
