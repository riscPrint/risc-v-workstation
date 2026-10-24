package spinalblocks

/** The diagram data, serialised as described in docs/FORMAT.md. */
object Model {
  final case class Loc(file: String, line: Int)

  final case class Design(top: String, modules: Seq[Module])

  final case class Module(name: String, className: String, loc: Option[Loc], instanceCount: Int, blackbox: Boolean,
                          ports: Seq[Port], instances: Seq[Instance], nodes: Seq[Node], nets: Seq[Net],
                          fsms: Seq[Fsm] = Nil)

  final case class FsmState(name: String, loc: Option[Loc])
  final case class FsmTransition(from: Option[String], to: Option[String], condition: Option[String],
                                 comment: Option[String], loc: Option[Loc])
  final case class Fsm(id: String, name: String, node: Option[String], register: String, kind: String,
                       loc: Option[Loc], states: Seq[FsmState], reset: Option[String], transitions: Seq[FsmTransition])

  final case class Port(name: String, dir: String, width: Int, tpe: String, group: String, groups: Seq[String],
                        loc: Option[Loc])

  final case class Instance(id: String, name: String, module: String, parent: Option[String], loc: Option[Loc])

  final case class Signal(name: String, width: Int, tpe: String, reg: Boolean, loc: Option[Loc])

  final case class Node(id: String, name: String, kind: String, parent: Option[String], compound: Boolean,
                        className: Option[String], loc: Option[Loc], signals: Seq[Signal], regCount: Int,
                        combCount: Int)

  sealed trait Endpoint
  final case class PortEp(port: String) extends Endpoint
  final case class InstEp(id: String, port: String) extends Endpoint
  final case class NodeEp(id: String) extends Endpoint

  final case class Net(id: String, name: String, width: Int, via: Seq[String], control: Boolean, clock: Boolean,
                       from: Endpoint, to: Seq[Endpoint])

  // ---- JSON ----
  private def opt[T](o: Option[T])(f: T => ujson.Value): ujson.Value = o.map(f).getOrElse(ujson.Null)
  private def loc(l: Option[Loc]): ujson.Value = opt(l)(l => ujson.Obj("file" -> l.file, "line" -> l.line))

  private def ep(e: Endpoint): ujson.Value = e match {
    case PortEp(p)     => ujson.Obj("kind" -> "port", "port" -> p)
    case InstEp(i, p)  => ujson.Obj("kind" -> "inst", "id" -> i, "port" -> p)
    case NodeEp(i)     => ujson.Obj("kind" -> "node", "id" -> i)
  }

  def toJson(d: Design): ujson.Value = ujson.Obj(
    "format" -> "spinalblocks",
    "version" -> 1,
    "top" -> d.top,
    "generated" -> java.time.Instant.now().toString,
    "modules" -> ujson.Obj.from(d.modules.map(m => m.name -> module(m)))
  )

  private def module(m: Module): ujson.Value = ujson.Obj(
    "name" -> m.name,
    "className" -> m.className,
    "loc" -> loc(m.loc),
    "instanceCount" -> m.instanceCount,
    "blackbox" -> m.blackbox,
    "ports" -> m.ports.map(p => ujson.Obj("name" -> p.name, "dir" -> p.dir, "width" -> p.width, "type" -> p.tpe,
      "group" -> p.group, "groups" -> p.groups, "loc" -> loc(p.loc))),
    "instances" -> m.instances.map(i => ujson.Obj("id" -> i.id, "name" -> i.name, "module" -> i.module,
      "parent" -> opt(i.parent)(ujson.Str(_)), "loc" -> loc(i.loc))),
    "nodes" -> m.nodes.map(n => ujson.Obj("id" -> n.id, "name" -> n.name, "kind" -> n.kind,
      "parent" -> opt(n.parent)(ujson.Str(_)), "compound" -> n.compound, "className" -> opt(n.className)(ujson.Str(_)),
      "loc" -> loc(n.loc),
      "signals" -> n.signals.map(s => ujson.Obj("name" -> s.name, "width" -> s.width, "type" -> s.tpe, "reg" -> s.reg,
        "loc" -> loc(s.loc))),
      "regCount" -> n.regCount, "combCount" -> n.combCount)),
    "nets" -> m.nets.map(n => ujson.Obj("id" -> n.id, "name" -> n.name, "width" -> n.width, "via" -> n.via,
      "control" -> n.control, "clock" -> n.clock, "from" -> ep(n.from), "to" -> n.to.map(ep))),
    "fsms" -> m.fsms.map(f => ujson.Obj("id" -> f.id, "name" -> f.name, "node" -> opt(f.node)(ujson.Str(_)),
      "register" -> f.register, "kind" -> f.kind, "loc" -> loc(f.loc),
      "states" -> f.states.map(s => ujson.Obj("name" -> s.name, "loc" -> loc(s.loc))),
      "reset" -> opt(f.reset)(ujson.Str(_)),
      "transitions" -> f.transitions.map(t => ujson.Obj("from" -> opt(t.from)(ujson.Str(_)), "to" -> opt(t.to)(ujson.Str(_)),
        "condition" -> opt(t.condition)(ujson.Str(_)), "comment" -> opt(t.comment)(ujson.Str(_)), "loc" -> loc(t.loc)))))
  )
}
