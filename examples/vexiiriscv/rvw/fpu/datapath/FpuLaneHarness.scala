package rvwvexii

import spinal.core._
import spinal.lib._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.Global
import vexiiriscv.decode.Decode
import vexiiriscv.execute._
import vexiiriscv.execute.fpu._
import vexiiriscv.riscv._

/** Unit transactions enter the execution lane. Fetch/decode/dispatch are outside scope.
  * The real lane decoder, unpacker, arithmetic, packer, WB and flag logic are retained.
  * Only one transaction is sent between resets. Operands and instruction stay stable.
  */
class FpuLaneBoundary(width: Int) extends FiberPlugin {
  val logic = during patch new Area {
    val lane = host[ExecuteLanePlugin]
    val io = new Bundle {
      val a,b,c = in Bits(width bits)
      val instruction = in Bits(32 bits)
      val rm = in Bits(3 bits)
      val start = in Bool()
      val y = out Bits(width bits)
      val flags = out Bits(5 bits)
      val done = out Bool()
    }
    io.setName("unit")
    // CSR requests are outside this arithmetic-unit boundary.
    host[CsrAccessPlugin].bus.get.write.valid.removeAssignments() := False
    val first = lane.ctrl(0)
    first.ctrlLink.up.valid.removeAssignments() := io.start
    first.up(first.LANE_SEL).removeAssignments() := io.start
    first.up(lane.LAYER_SEL).removeAssignments() := lane.getLayerId(host[FpuAddPlugin].layer)
    val instruction = Bits(32 bits)
    instruction := io.instruction
    instruction(14 downto 12) := io.rm
    first.up(Decode.UOP).removeAssignments() := instruction.resized
    first.up(Global.TRAP).removeAssignments() := False
    first.up(Global.HART_ID).removeAssignments() := 0
    first.up(Decode.UOP_ID).removeAssignments() := 0
    val rd = Decode.rfaKeys.get(RD)
    first.up(rd.ENABLE).removeAssignments() := True
    first.up(rd.PHYS).removeAssignments() := 5
    val scalar = io.instruction(6 downto 0) === B(0x53, 7 bits)
    val f5 = io.instruction(31 downto 27).asUInt
    val integerSource = scalar && f5 === 26
    val integerDestination = scalar && f5 === 24
    first.up(rd.RFID).removeAssignments() := Mux(integerDestination,
      U(rd.idOf(IntRegFile), rd.rfIdWidth bits), U(rd.idOf(FloatRegFile), rd.rfIdWidth bits))
    val fused = List(0x43,0x47,0x4b,0x4f).map(op => io.instruction(6 downto 0) === B(op,7 bits)).orR
    val binary = fused || scalar && (f5 <= 5 || f5 === 20)
    for((access,index) <- List(RS1,RS2,RS3).zipWithIndex) {
      val keys = Decode.rfaKeys.get(access)
      first.up(keys.ENABLE).removeAssignments() := (if(index==0) True else if(index==1) binary else fused)
      first.up(keys.PHYS).removeAssignments() := index+1
      if(index==0) {
        first.up(keys.RFID).removeAssignments() := Mux(integerSource,
          U(keys.idOf(IntRegFile),keys.rfIdWidth bits), U(keys.idOf(FloatRegFile),keys.rfIdWidth bits))
      } else first.up(keys.RFID).removeAssignments() := keys.idOf(FloatRegFile)
    }
    for((resource,payload) <- lane.rfStageables) {
      val value = resource.access match {
        case RS1 => io.a
        case RS2 => io.b
        case RS3 => io.c
        case _ => io.a
      }
      // The API uses the same stageable for the original RF value and bypassed reads.
      // At the execute entrance this cuts register-file and bypass data dependencies.
      lane.execute(0).up(payload).removeAssignments() := value.resized
    }
    for(ctrl <- lane.idToCtrl.values) {
      ctrl.upIsCancel.removeAssignments() := False
      ctrl.downIsCancel.removeAssignments() := False
    }
    val fp = host.list[WriteBackPlugin].find(_.rf == FloatRegFile).get.logic.write.port
    val integer = host.list[WriteBackPlugin].find(_.rf == IntRegFile).get.logic.write.port
    val valid = fp.valid || integer.valid
    val result = Reg(Bits(width bits))
    when(fp.valid) { result := fp.data.resized }
    when(integer.valid) { result := integer.data.resized }
    val settled = RegNext(RegNext(valid) init(False)) init(False)
    val done = RegInit(False) setWhen(settled)
    io.y := result
    io.flags := host[FpuCsrPlugin].api.flags.asBits
    io.done := done
  }
}

object FpuLaneHarnessMain extends App {
  require(args.length == 2, "width output-directory")
  val width = args(0).toInt
  SpinalConfig(targetDirectory=args(1), inlineRom=true).generateVerilog {
  val p = new ParamSimple()
  p.xlen = width
  p.addISA("m", "a", "f", "c")
  if(width == 64) p.addISA("d")
  p.fixIsaParams()
  val plugins = p.plugins()
  plugins += new FpuLaneBoundary(width)
  ParamSimple.setPma(plugins, ParamSimple.defaultPma)
  VexiiRiscv(plugins)
  }
}
