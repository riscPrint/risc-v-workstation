package rvwsmp

/** Simulation-only CLINT and seven-source, machine-context PLIC register service. */
class Devices(harts: Int) {
  private val mask64 = (BigInt(1) << 64)-1
  val msip = Array.fill(harts)(false)
  val compare = Array.fill(harts)(mask64)
  var time = BigInt(0)
  val priority = Array.fill(8)(0)
  val enable = Array.fill(harts)(0)
  val threshold = Array.fill(harts)(0)
  private val level = Array.fill(8)(false)
  private val busy = Array.fill(8)(false)
  def source(id: Int, high: Boolean): Unit = { require(id>=1 && id<=7); level(id)=high }
  def claim(h: Int): Int = (1 to 7).filter(i => level(i) && !busy(i) && (enable(h)&(1 << i))!=0 && priority(i)>threshold(h))
    .sortBy(i => (-priority(i),i)).headOption.getOrElse(0)
  def external(h: Int): Boolean = claim(h)!=0
  def contains(a: Long): Boolean = (a>=0x2000000L && a<0x2010000L) || (a>=0xc000000L && a<0xc400000L)
  private def word(a: Long, claimRead: Boolean): BigInt = {
    if(a>=0x2000000L && a<0x2000000L+4*harts) BigInt(if(msip(((a-0x2000000L)/4).toInt)) 1 else 0)
    else if(a>=0x2004000L && a<0x2004000L+8*harts) {
      val off=a-0x2004000L; (compare((off/8).toInt) >> ((off%8).toInt*8)) & 0xffffffffL
    } else if(a==0x200bff8L) time & 0xffffffffL
    else if(a==0x200bffcL) (time>>32)&0xffffffffL
    else if(a>=0xc000000L && a<0xc000020L) BigInt(priority(((a-0xc000000L)/4).toInt))
    else if(a==0xc001000L) BigInt((1 to 7).filter(i=>level(i) && !busy(i)).map(1 << _).sum)
    else if(a>=0xc002000L && a<0xc002000L+harts*0x80 && (a-0xc002000L)%0x80==0) BigInt(enable(((a-0xc002000L)/0x80).toInt))
    else if(a>=0xc200000L && a<0xc200000L+harts*0x1000) {
      val h=((a-0xc200000L)/0x1000).toInt
      (a-0xc200000L)%0x1000 match {
        case 0 => BigInt(threshold(h))
        case 4 => val id=claim(h); if(claimRead && id!=0) busy(id)=true; BigInt(id)
        case _ => BigInt(0)
      }
    } else BigInt(0)
  }
  def read(a: Long, size: Int): BigInt = {
    require(size==4 || size==8)
    val low=word(a,true)
    if(size==8) low | (word(a+4,true)<<32) else low
  }
  def write(a: Long, data: BigInt, size: Int): Unit = {
    require(size==4 || size==8)
    def store(a: Long, d: Long): Unit = {
      if(a>=0x2000000L && a<0x2000000L+4*harts) msip(((a-0x2000000L)/4).toInt)=(d&1)!=0
      else if(a>=0x2004000L && a<0x2004000L+8*harts) {
        val off=a-0x2004000L; val h=(off/8).toInt; val shift=(off%8).toInt*8
        compare(h)=(compare(h)&(mask64 ^ (BigInt(0xffffffffL)<<shift))) | (BigInt(d&0xffffffffL)<<shift)
      } else if(a==0x200bff8L || a==0x200bffcL) {
        val shift=if(a==0x200bff8L) 0 else 32
        time=(time&(mask64 ^ (BigInt(0xffffffffL)<<shift))) | (BigInt(d&0xffffffffL)<<shift)
      } else if(a>=0xc000004L && a<0xc000020L) priority(((a-0xc000000L)/4).toInt)=(d&7).toInt
      else if(a>=0xc002000L && a<0xc002000L+harts*0x80 && (a-0xc002000L)%0x80==0) enable(((a-0xc002000L)/0x80).toInt)=(d&254).toInt
      else if(a>=0xc200000L && a<0xc200000L+harts*0x1000) {
        val h=((a-0xc200000L)/0x1000).toInt
        (a-0xc200000L)%0x1000 match {
          case 0 => threshold(h)=(d&7).toInt
          case 4 => if(d>=1 && d<=7 && (enable(h)&(1 << d.toInt))!=0) busy(d.toInt)=false
          case _ =>
        }
      }
    }
    store(a,(data&0xffffffffL).toLong)
    if(size==8) store(a+4,((data>>32)&0xffffffffL).toLong)
  }
}
