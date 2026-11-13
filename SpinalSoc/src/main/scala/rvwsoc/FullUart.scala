package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.com.uart._

class UartModem extends Bundle {
  val cts_n, dsr_n, ri_n, dcd_n = in Bool()
  val rts_n, dtr_n, out1_n, out2_n = out Bool()
}

/** Word-spaced 16550 register UART with selectable one-byte/16-byte FIFOs. */
class Uart16550Full extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32)))
    val serial = master(Uart())
    val modem = new UartModem
    val rx_ready_n, tx_ready_n = out Bool()
    val irq = out Bool()
  }
  val impl = new BlackBox {
    setBlackBoxName("rvw_uart16550")
    val io = new Bundle {
      val clk, reset = in Bool()
      val PADDR = in Bits(8 bits)
      val PSEL, PENABLE, PWRITE = in Bool()
      val PWDATA = in Bits(32 bits)
      val PRDATA = out Bits(32 bits)
      val PREADY, PSLVERROR = out Bool()
      val rxd = in Bool()
      val txd, irq, rx_ready_n, tx_ready_n = out Bool()
      val cts_n, dsr_n, ri_n, dcd_n = in Bool()
      val rts_n, dtr_n, out1_n, out2_n = out Bool()
    }
    noIoPrefix()
    mapCurrentClockDomain(clock=io.clk, reset=io.reset)
    addRTLPath(new java.io.File(getClass.getResource("/rvwsoc/uart16550.sv").toURI).getPath)
  }
  impl.io.PADDR := io.bus.PADDR.asBits
  impl.io.PSEL := io.bus.PSEL.lsb
  impl.io.PENABLE := io.bus.PENABLE
  impl.io.PWRITE := io.bus.PWRITE
  impl.io.PWDATA := io.bus.PWDATA
  io.bus.PRDATA := impl.io.PRDATA
  io.bus.PREADY := impl.io.PREADY
  io.bus.PSLVERROR := impl.io.PSLVERROR
  impl.io.rxd := io.serial.rxd
  io.serial.txd := impl.io.txd
  impl.io.cts_n := io.modem.cts_n; impl.io.dsr_n := io.modem.dsr_n
  impl.io.ri_n := io.modem.ri_n; impl.io.dcd_n := io.modem.dcd_n
  io.modem.rts_n := impl.io.rts_n; io.modem.dtr_n := impl.io.dtr_n
  io.modem.out1_n := impl.io.out1_n; io.modem.out2_n := impl.io.out2_n
  io.irq := impl.io.irq
  io.rx_ready_n := impl.io.rx_ready_n; io.tx_ready_n := impl.io.tx_ready_n
}


object FullUartGenerate extends App {
  SpinalConfig(targetDirectory=args(0)).generateVerilog(new Uart16550Full)
}
