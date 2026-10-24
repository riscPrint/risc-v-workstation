package spinaldb

import scala.util.control.NonFatal

/** Class names do not establish library membership. Require the anchor's loader and code source,
  * and the exact class resolved by that loader. Missing origin information fails closed. */
private[spinaldb] object LibraryClasses {
  private def source(c: Class[_]): Option[java.net.URL] =
    try Option(c.getProtectionDomain).flatMap(d => Option(d.getCodeSource)).flatMap(s => Option(s.getLocation))
    catch { case NonFatal(_) => None }

  private val originMemo = new java.util.concurrent.ConcurrentHashMap[(Class[_], Class[_]), java.lang.Boolean]()
  def from(c: Class[_], anchor: Class[_]): Boolean = originMemo.computeIfAbsent((c, anchor), { _ =>
    try {
      c.getClassLoader == anchor.getClassLoader && source(anchor).exists(s => source(c).contains(s)) &&
        Class.forName(c.getName, false, anchor.getClassLoader) == c
    } catch { case NonFatal(_) | _: LinkageError => false }
  }).booleanValue()

  /** One exact-class check for all semantic objects. No package-name shortcut is valid. */
  def exact(c: Class[_], expected: Class[_]): Boolean = c == expected &&
    (isJdk(c) || isSpinal(c) || isScala(c))

  private val signalClasses: Set[Class[_]] = Set(classOf[spinal.core.Bool], classOf[spinal.core.Bits],
    classOf[spinal.core.UInt], classOf[spinal.core.SInt], classOf[spinal.core.SpinalEnumCraft[_]])
  def signal(c: Class[_]): Boolean = signalClasses(c) && isSpinal(c)

  def isSpinal(c: Class[_]): Boolean = from(c, classOf[spinal.core.Bool])
  def isSpinalLib(c: Class[_]): Boolean = from(c, classOf[spinal.lib.Stream[_]])
  def isSpinalDsl(c: Class[_]): Boolean = from(c, classOf[spinal.idslplugin.ValCallback])
  def isScala(c: Class[_]): Boolean = from(c, classOf[scala.collection.immutable.List[_]])

  /** java.base is loaded by the bootstrap loader and has no code source. */
  def isJdk(c: Class[_]): Boolean = c.getClassLoader == null && c.getModule == classOf[Object].getModule
}
