// Value-sensitive gate IFT for a flattened, simplemap Yosys design.
#include "kernel/yosys.h"
#include "kernel/sigtools.h"
USING_YOSYS_NAMESPACE
PRIVATE_NAMESPACE_BEGIN

struct RvwIftPass : public Pass {
    RvwIftPass() : Pass("rvw_ift", "add Boolean data and control-flow taint logic") {}
    void help() override {
        log("rvw_ift\n    Run after hierarchy -top TOP; proc; flatten; techmap; simplemap.\n");
        log("    Adds __t data ports. One public rising-edge clock. Apply public reset.\n");
        log("    No declassification, X/Z, init attributes, blackboxes or memories.\n");
    }
    void execute(std::vector<std::string> args, RTLIL::Design *design) override {
        extra_args(args, 1, design);
        auto m = design->top_module();
        if (!m || GetSize(design->modules()) != 1 || !design->full_selection())
            log_cmd_error("Require one fully selected flattened top module.\n");
        if (!m->memories.empty() || !m->processes.empty() || m->get_bool_attribute(ID::blackbox))
            log_cmd_error("Memories, processes and blackboxes are unmodeled.\n");
        SigMap sm(m);
        pool<SigBit> bits, driven, clocks;
        auto wires = m->wires().to_vector();
        auto cells = m->cells().to_vector();
        for (auto w : wires) {
            if (w->attributes.count(ID::init)) log_cmd_error("Initial state is unmodeled.\n");
            if (w->port_input && w->port_output) log_cmd_error("Inout ports are unmodeled.\n");
            if ((w->port_input || w->port_output) && m->wire(RTLIL::escape_id(RTLIL::unescape_id(w->name)+"__t")))
                log_cmd_error("Taint port name already exists.\n");
            for (auto b : sm(SigSpec(w))) {
                if (!b.wire) {
                    if (b.data != State::S0 && b.data != State::S1) log_cmd_error("X/Z constant is unmodeled.\n");
                } else bits.insert(b);
                if (w->port_input && (!b.wire || !driven.insert(b).second))
                    log_cmd_error("Aliased input or multiple driver is unmodeled.\n");
            }
        }
        for (auto c : cells) {
            if (!c->type.in(ID($_NOT_), ID($_AND_), ID($_OR_), ID($_XOR_), ID($_MUX_), ID($_DFF_P_)))
                log_cmd_error("Unmodeled cell %s (%s).\n", log_id(c), log_id(c->type));
            for (auto conn : c->connections()) for (auto b : sm(conn.second))
                if (!b.wire && b.data != State::S0 && b.data != State::S1)
                    log_cmd_error("X/Z cell input is unmodeled.\n");
            if (c->type == ID($_DFF_P_)) clocks.insert(sm(c->getPort(ID::C)).as_bit());
            auto y = sm(c->getPort(c->type == ID($_DFF_P_) ? ID::Q : ID::Y)).as_bit();
            if (!y.wire || !driven.insert(y).second) log_cmd_error("Multiple or constant driver.\n");
        }
        if (GetSize(clocks) > 1) log_cmd_error("Require one public rising-edge clock.\n");
        for (auto b : clocks) {
            int count=0;
            for (auto w : wires) if (w->port_input && w->width == 1 && sm(SigSpec(w)).as_bit() == b) count++;
            if (count != 1) log_cmd_error("Clock must be one scalar public input.\n");
        }
        for (auto b : bits) if (!driven.count(b)) log_cmd_error("Undriven bit is unmodeled.\n");
        // Complete validation before changing the module.
        dict<SigBit, SigBit> taints;
        for (auto b : bits) taints[b] = SigBit(m->addWire(NEW_ID));
        auto t = [&](SigBit b) -> SigBit { b=sm(b); return b.wire ? taints.at(b) : SigBit(State::S0); };
        for (auto w : wires) if (w->port_input || w->port_output) {
            if (w->port_input && w->width == 1 && clocks.count(sm(SigSpec(w)).as_bit())) {
                m->connect(t(SigBit(w)), State::S0); continue;
            }
            auto tw = m->addWire(RTLIL::escape_id(RTLIL::unescape_id(w->name)+"__t"), w->width);
            tw->port_input=w->port_input; tw->port_output=w->port_output;
            for (int i=0; i<w->width; ++i) {
                if (w->port_input) m->connect(t(SigBit(w,i)), SigBit(tw,i));
                else m->connect(SigBit(tw,i), t(SigBit(w,i)));
            }
        }
        for (auto c : cells) {
            if (c->type == ID($_DFF_P_)) {
                m->addDff(NEW_ID, c->getPort(ID::C), t(c->getPort(ID::D).as_bit()), t(c->getPort(ID::Q).as_bit()));
                continue;
            }
            std::vector<SigBit> in;
            for (auto p : {ID::A, ID::B, ID::S}) if (c->hasPort(p)) in.push_back(sm(c->getPort(p)).as_bit());
            SigSpec poss[2] = {State::S0, State::S0};
            for (int mask=0; mask < (1 << GetSize(in)); ++mask) {
                bool a=mask&1, b=mask&2, s=mask&4;
                int result = c->type==ID($_NOT_) ? !a : c->type==ID($_AND_) ? a&&b :
                    c->type==ID($_OR_) ? a||b : c->type==ID($_XOR_) ? a!=b : s ? b : a;
                SigSpec term=State::S1;
                for (int i=0; i<GetSize(in); ++i) {
                    SigSpec val = (mask & (1<<i)) ? SigSpec(in[i]) : m->Not(NEW_ID,in[i]);
                    term=m->And(NEW_ID,term,m->Or(NEW_ID,t(in[i]),val));
                }
                poss[result]=m->Or(NEW_ID,poss[result],term);
            }
            m->connect(t(c->getPort(ID::Y).as_bit()), m->And(NEW_ID,poss[0],poss[1]));
        }
        m->fixup_ports();
        log("Added rvw_ift taint logic to %s. Public reset is required before observation.\n",log_id(m));
    }
} RvwIftPass;
PRIVATE_NAMESPACE_END
