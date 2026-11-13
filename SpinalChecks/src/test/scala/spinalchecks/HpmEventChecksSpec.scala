package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class HpmEventChecksSpec extends AnyFunSuite {
  class Top extends Component {
    val control = in Bits(64 bits)
    val controlWrite = in Bool()
    val data = in Bits(64 bits)
    val e0 = in UInt(4 bits)
    val e1 = in UInt(4 bits)
    val mode = in UInt(2 bits)
    val virtualized = in Bool()
    val count = in UInt(8 bits)
    val write = in Bool()
    val countData = in UInt(8 bits)
    val inhibit = in Bool()
    HpmEventChecks.bind("events",control,controlWrite,data,Seq(e0,e1),mode,virtualized,count,write,countData,inhibit)
  }
  test("independent programmable events and five mode filters detect seeded faults") {
    val (cfg,_) = SpinalChecks.install(SpinalConfig(targetDirectory="generated/hpm-events"),ChecksConfig(mode=Mode.Monitor))
    val compiled = SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("hpm-events").withVerilator.compile(new Top)
    for(fault <- Seq("none","selector","count")) compiled.doSim(name=fault,seed=31) { d =>
      d.control #= 0;d.controlWrite #= false;d.data #= 0;d.e0 #= 0;d.e1 #= 0
      d.mode #= 3;d.virtualized #= false;d.count #= 0;d.write #= false;d.countData #= 0;d.inhibit #= false
      d.clockDomain.forkStimulus(10);d.clockDomain.waitSampling(5)
      var control=BigInt(0);var count=0
      def step(next: Option[BigInt]=None, mode:Int=3, virt:Boolean=false, e0:Int=0,e1:Int=0, inhibit:Boolean=false,write:Option[Int]=None):Unit={
        d.clockDomain.waitFallingEdge()
        d.control #= (if(fault=="selector") control ^ 1 else control)
        d.controlWrite #= next.nonEmpty;d.data #= next.getOrElse(BigInt(0))
        d.mode #= mode;d.virtualized #= virt;d.e0 #= e0;d.e1 #= e1;d.inhibit #= inhibit
        d.write #= write.nonEmpty;d.countData #= write.getOrElse(0).toLong
        d.count #= (if(fault=="count") (count+1)&255 else count)
        d.clockDomain.waitSampling()
        val filter = if(mode==3) 62 else if(mode==1 && !virt) 61 else if(mode==0 && !virt) 60 else if(mode==1) 59 else 58
        if(!inhibit && !control.testBit(filter) && mode!=2 && !(mode==3 && virt)) {
          count=(count+(if(control.testBit(0))e0 else 0)+(if(control.testBit(1))e1 else 0))&255
        }
        write.foreach(v=>count=v)
        next.foreach(v=>control=v & (((BigInt(1)<<5)-1)<<58 | 3))
      }
      step(Some(3));step(e0=2,e1=3)
      for((mode,virt,bit) <- Seq((3,false,62),(1,false,61),(0,false,60),(1,true,59),(0,true,58))) {
        step(Some((BigInt(1)<<bit)|3));step(mode=mode,virt=virt,e0=2,e1=3)
        step(Some(3));step(mode=mode,virt=virt,e0=2,e1=3)
      }
      step(Some(1));step(e0=2,e1=9);step(e0=2,inhibit=true);step(e0=2,write=Some(250));step(e0=9)
      step(mode=2,e0=7);step(mode=3,virt=true,e0=7)
      step();step()
      val kinds=ChecksSim.firings(d).map(_.check.kind).toSet
      assert(kinds == (fault match {case "selector"=>Set("hpm.event_control");case "count"=>Set("hpm.count");case _=>Set.empty[String]}))
    }
  }
}
