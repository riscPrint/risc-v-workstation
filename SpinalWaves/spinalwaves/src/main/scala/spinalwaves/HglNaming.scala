package spinalwaves

import spinal.core._

/** The shared naming contract used by SpinalWaves and SpinalTrace. Never changes RTL names. */
object HglNaming {
  /** Instance path from the toplevel, excluding the toplevel itself. */
  def instancePath(c: Component): Seq[String] =
    if (c == null || c.parent == null) Seq.empty else instancePath(c.parent) :+ c.getName()

  /** Typed root path and dot-separated field path. Vec indices are decimal strings. */
  def hglPath(bt: BaseType): (String, String) = {
    val (root, fields) = localPath(bt)
    ((instancePath(bt.component) :+ root).mkString("."), fields.mkString("."))
  }

  /** Actual RTL instance/signal path, excluding the toplevel. */
  def rtlPath(bt: BaseType): String = (instancePath(bt.component) :+ bt.getName()).mkString(".")

  private[spinalwaves] def dataPath(data: Data): (Data, Seq[String]) = {
    // Fixed-point wrappers own their raw signal through refOwner, without setting Data.parent.
    val parent = Option(data.parent).orElse(data.refOwner match {
      case multi: MultiData if multi.elements.exists { case (_, child) => child eq data } => Some(multi)
      case _ => None
    })
    parent match {
      case None => (data, Seq.empty)
      case Some(owner) =>
        val (root, path) = dataPath(owner)
        val field = owner match {
          case multi: MultiData => multi.elements.find { case (_, child) => child eq data }.map(_._1)
          case _ => None
        }
        // An empty member name is Spinal's transparent raw fixed-point representation.
        (root, path ++ field.orElse(Option(data.getPartialName())).filter(_.nonEmpty).toSeq)
    }
  }

  private[spinalwaves] def localPath(bt: BaseType): (String, Seq[String]) = {
    val (root, fields) = dataPath(bt)
    val areas = root.getRefOwnersChain().collect {
      case a: Area if a.component == bt.component && a.isNamed => a
    }
    if (areas.isEmpty) (Option(root.getName()).filter(_.nonEmpty).getOrElse("io"), fields)
    else {
      def relative(child: Nameable, owner: Nameable): String = {
        val prefix = owner.getName() + "_"
        val full = child.getName()
        if (full.startsWith(prefix)) full.substring(prefix.length) else full
      }
      val areaFields = areas.sliding(2).collect { case Seq(a, b) => relative(b, a) }.toSeq
      (areas.head.getName(), areaFields ++ Seq(relative(root, areas.last)) ++ fields)
    }
  }
}
