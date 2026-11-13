// Branch target models: multi-level set-associative BTB, return address stack with
// checkpoint repair policies, and indirect target predictors (last-target BTB,
// ITTAGE after Seznec, JWAC-2 2011). Owner-written; not bit-exact.
#pragma once
#include "common.h"

namespace csim {

class Btb {
public:
    struct Way { bool valid = false; uint64_t tag = 0, target = 0; uint8_t kind = 0; uint64_t stamp = 0; };
    struct Level {
        uint64_t sets; unsigned ways, tag_bits, latency; std::vector<Way> w;
        uint64_t lookups = 0, hits = 0, fills = 0, evictions = 0;
    };
    std::vector<Level> levels; unsigned shift; uint64_t clock = 0; unsigned target_bits;
    bool alloc_not_taken;

    explicit Btb(const Config& c) {
        shift = unsigned(c.u("pc_shift", 1, 0, 63));
        target_bits = unsigned(c.u("target_bits", 32, 1, 64));
        alloc_not_taken = c.flag("allocate_not_taken", false);
        size_t n = c.list("levels");
        auto add = [&](const Config& l, uint64_t def_entries, unsigned def_ways, unsigned def_lat) {
            Level v; uint64_t entries = l.u("entries", def_entries, 1, 1u << 24); v.ways = unsigned(l.u("ways", def_ways, 1, 64));
            if (entries % v.ways || !pow2(entries / v.ways)) throw Error("BTB entries/ways must give a power-of-two set count");
            v.sets = entries / v.ways; v.tag_bits = unsigned(l.u("tag_bits", 0, 0, 64)); v.latency = unsigned(l.u("latency", def_lat, 0, 64));
            v.w.assign(entries, Way()); levels.push_back(std::move(v));
        };
        if (!n) add(c, 4096, 4, 0);
        for (size_t i = 0; i < n; ++i) add(c.at("levels", i), 1024, 4, unsigned(i));
    }
    uint64_t tag_of(const Level& l, uint64_t pc) const {
        uint64_t t = (pc >> shift) >> log2u(l.sets);
        return l.tag_bits ? (t ^ (t >> l.tag_bits)) & mask(l.tag_bits) : t;
    }
    Way* find(Level& l, uint64_t pc) {
        uint64_t set = (pc >> shift) & (l.sets - 1), tag = tag_of(l, pc);
        for (unsigned k = 0; k < l.ways; ++k) { Way& w = l.w[set * l.ways + k]; if (w.valid && w.tag == tag) return &w; }
        return nullptr;
    }
    void fill(Level& l, uint64_t pc, uint64_t target, uint8_t kind) {
        uint64_t set = (pc >> shift) & (l.sets - 1), tag = tag_of(l, pc);
        Way* victim = nullptr;
        for (unsigned k = 0; k < l.ways; ++k) {
            Way& w = l.w[set * l.ways + k];
            if (w.valid && w.tag == tag) { victim = &w; break; }
            if (!victim || (!w.valid && victim->valid) || (w.valid == victim->valid && w.stamp < victim->stamp)) victim = &w;
        }
        if (victim->valid && victim->tag != tag) ++l.evictions;
        if (!victim->valid || victim->tag != tag) ++l.fills;
        victim->valid = true; victim->tag = tag; victim->kind = kind; victim->stamp = ++clock;
        // Stored targets keep the low target_bits; the upper bits come from the PC.
        victim->target = (pc & ~mask(target_bits)) | (target & mask(target_bits));
    }
    struct Hit { int level = -1; uint64_t target = 0; uint8_t kind = 0; };
    // Look up all levels in order; a hit in a lower level refills the upper levels.
    Hit lookup(uint64_t pc) {
        Hit h;
        for (size_t i = 0; i < levels.size(); ++i) {
            Level& l = levels[i]; ++l.lookups;
            if (Way* w = find(l, pc)) {
                ++l.hits; w->stamp = ++clock; h.level = int(i); h.target = w->target; h.kind = w->kind;
                for (size_t j = 0; j < i; ++j) fill(levels[j], pc, w->target, w->kind);
                return h;
            }
        }
        return h;
    }
    void update(uint64_t pc, uint8_t kind, bool taken, uint64_t target) {
        if (!taken && !alloc_not_taken) {
            return;
        }
        for (auto& l : levels) fill(l, pc, taken ? target : 0, kind);
    }
    Storage storage() const {
        Storage s;
        for (size_t i = 0; i < levels.size(); ++i) {
            auto& l = levels[i];
            unsigned tb = l.tag_bits ? l.tag_bits : unsigned(64 - shift - log2u(l.sets));
            s.add("level" + std::to_string(i), uint64_t(l.w.size()) * (1 + tb + target_bits + 3 + log2u(l.ways)));
        }
        return s;
    }
    Json stats() const {
        Json a = Json::array();
        for (auto& l : levels) {
            Json j = Json::object(); j["entries"] = uint64_t(l.w.size()); j["ways"] = l.ways; j["latency"] = l.latency;
            j["lookups"] = l.lookups; j["hits"] = l.hits; j["fills"] = l.fills; j["evictions"] = l.evictions; a.push(j);
        }
        return a;
    }
};

class Ras {
public:
    enum Repair { NONE, POINTER, POINTER_TOP, FULL };
    std::vector<uint64_t> st; size_t top = 0, count = 0; Repair repair;
    uint64_t pushes = 0, pops = 0, overflows = 0, underflows = 0, repairs = 0;
    explicit Ras(const Config& c) {
        st.assign(c.u("entries", 32, 1, 1u << 16), 0);
        std::string r = c.choice("repair", "pointer_top", {"none", "pointer", "pointer_top", "full"});
        repair = r == "none" ? NONE : r == "pointer" ? POINTER : r == "pointer_top" ? POINTER_TOP : FULL;
    }
    void push(uint64_t a) {
        ++pushes; top = (top + 1) % st.size(); st[top] = a;
        if (count == st.size()) ++overflows; else ++count;
    }
    bool pop(uint64_t& a) {
        ++pops;
        if (!count) { ++underflows; a = 0; return false; }
        a = st[top]; top = (top + st.size() - 1) % st.size(); --count; return true;
    }
    struct Checkpoint { size_t top = 0, count = 0; uint64_t value = 0; std::vector<uint64_t> full; };
    Checkpoint save() const {
        Checkpoint c; c.top = top; c.count = count; c.value = st[top];
        if (repair == FULL) c.full = st;
        return c;
    }
    void restore(const Checkpoint& c) {
        if (repair == NONE) return;
        ++repairs;
        top = c.top; count = c.count;
        if (repair == POINTER_TOP) st[top] = c.value;
        if (repair == FULL) st = c.full;
    }
    Storage storage() const { Storage s; s.add("entries", st.size() * 64); s.add("pointer", 2 * log2u(st.size() + 1)); return s; }
    Json stats() const {
        Json j = Json::object(); j["entries"] = uint64_t(st.size());
        const char* names[] = {"none", "pointer", "pointer_top", "full"}; j["repair"] = names[repair];
        j["pushes"] = pushes; j["pops"] = pops; j["overflows"] = overflows; j["underflows"] = underflows; j["repairs"] = repairs;
        return j;
    }
};

struct IndMeta {
    uint64_t pred = 0; bool valid = false;
    int provider = -1, alt = -1; uint32_t base_idx = 0; uint32_t idx[32]; uint32_t tag[32];
    bool from_alt = false; uint64_t alt_target = 0;
};

class Indirect {
public:
    virtual ~Indirect() = default;
    virtual std::string name() const = 0;
    virtual void predict(uint64_t pc, IndMeta& m) = 0;
    virtual void update(uint64_t pc, uint64_t target, const IndMeta& m) = 0;
    virtual void history(uint64_t, int, bool, uint64_t) {}
    virtual Storage storage() const = 0;
    virtual Json stats() const { return Json::object(); }
};

// Indirect targets from the BTB entry (last observed target).
class BtbIndirect : public Indirect {
public:
    std::string name() const override { return "btb"; }
    void predict(uint64_t, IndMeta&) override {}
    void update(uint64_t, uint64_t, const IndMeta&) override {}
    Storage storage() const override { return Storage(); }
};

class Ittage : public Indirect {
    struct Entry { uint32_t tag = 0; uint64_t target = 0; uint8_t ctr = 0, u = 0; };
    struct Base { uint64_t target = 0; uint8_t ctr = 0; };
    struct Table { uint64_t entries; unsigned log, tag_bits, hist; std::vector<Entry> e; Folded fi, ft; };
    std::vector<Table> tabs; std::vector<Base> base; uint64_t base_entries; unsigned shift, target_bits;
    History h; uint64_t u_period, updates = 0; Rng rng{7};
    std::vector<uint64_t> provider_count; uint64_t base_used = 0, allocs = 0;
public:
    explicit Ittage(const Config& c) {
        shift = unsigned(c.u("pc_shift", 1, 0, 63));
        target_bits = unsigned(c.u("target_bits", 32, 1, 64));
        base_entries = c.u("base_entries", 256, 1, 1u << 22);
        if (!pow2(base_entries)) throw Error("ittage base_entries must be a power of two");
        base.assign(base_entries, Base());
        u_period = c.u("u_reset_period", 64 * 1024, 0);
        size_t n = c.list("tables");
        struct S { uint64_t e; unsigned h, t; };
        std::vector<S> spec;
        if (!n) { unsigned hs[] = {4, 8, 16, 32, 64, 128}; for (unsigned x : hs) spec.push_back({256, x, 10}); }
        for (size_t i = 0; i < n; ++i) { auto t = c.at("tables", i); spec.push_back({t.u("entries", 256, 1, 1u << 22), unsigned(t.u("history", 8, 1, 4096)), unsigned(t.u("tag_bits", 10, 1, 24))}); }
        if (spec.size() > 32) throw Error("too many ITTAGE tables");
        unsigned maxh = 1;
        for (auto& s : spec) {
            if (!pow2(s.e)) throw Error("ittage table entries must be a power of two");
            Table t; t.entries = s.e; t.log = log2u(s.e); t.tag_bits = s.t; t.hist = s.h; t.e.assign(s.e, Entry());
            t.fi = Folded(s.h, t.log); t.ft = Folded(s.h, s.t); tabs.push_back(std::move(t)); maxh = std::max(maxh, s.h);
        }
        h = History(maxh + 1);
        provider_count.assign(tabs.size(), 0);
    }
    std::string name() const override { return "ittage"; }
    void predict(uint64_t pc, IndMeta& m) override {
        uint64_t p = pc >> shift;
        m.base_idx = uint32_t(p & (base_entries - 1));
        m.provider = m.alt = -1;
        for (size_t i = 0; i < tabs.size(); ++i) {
            auto& t = tabs[i];
            m.idx[i] = uint32_t((p ^ (p >> (t.log + 1)) ^ t.fi.comp ^ (i * 0x5bd1)) & (t.entries - 1));
            m.tag[i] = uint32_t((p ^ (p >> 3) ^ (t.ft.comp << 1) ^ t.ft.comp) & mask(t.tag_bits));
        }
        for (int i = int(tabs.size()) - 1; i >= 0; --i)
            if (tabs[i].e[m.idx[i]].tag == m.tag[i] && tabs[i].e[m.idx[i]].target) { if (m.provider < 0) m.provider = i; else { m.alt = i; break; } }
        uint64_t alt = m.alt >= 0 ? tabs[m.alt].e[m.idx[m.alt]].target : base[m.base_idx].target;
        m.alt_target = alt;
        if (m.provider >= 0) {
            const Entry& e = tabs[m.provider].e[m.idx[m.provider]];
            m.from_alt = e.ctr == 0 && alt;
            m.pred = m.from_alt ? alt : e.target;
        } else { m.pred = base[m.base_idx].target; m.from_alt = false; }
        m.valid = m.pred != 0;
    }
    void update(uint64_t pc, uint64_t target, const IndMeta& m) override {
        (void)pc; ++updates;
        uint64_t tg = target;
        bool correct = m.pred == tg;
        if (m.provider >= 0) {
            provider_count[m.provider]++;
            Entry& e = tabs[m.provider].e[m.idx[m.provider]];
            if (e.target == tg) { if (e.ctr < 3) ++e.ctr; }
            else if (e.ctr) --e.ctr; else e.target = tg;
            if ((e.target == tg) != (m.alt_target == tg)) { if (e.target == tg) { if (e.u < 1) ++e.u; } else if (e.u) --e.u; }
        } else ++base_used;
        Base& b = base[m.base_idx];
        if (m.provider < 0 || m.from_alt) {
            if (b.target == tg) { if (b.ctr < 3) ++b.ctr; } else if (b.ctr) --b.ctr; else b.target = tg;
        }
        if (!correct && m.provider < int(tabs.size()) - 1) {
            int start = m.provider + 1; bool done = false;
            for (int i = start; i < int(tabs.size()); ++i) {
                Entry& e = tabs[i].e[m.idx[i]];
                if (e.u == 0) { e.tag = m.tag[i]; e.target = tg; e.ctr = 0; done = true; ++allocs; break; }
            }
            if (!done) for (int i = start; i < int(tabs.size()); ++i) { Entry& e = tabs[i].e[m.idx[i]]; if (e.u) --e.u; }
        }
        if (u_period && updates % u_period == 0) for (auto& t : tabs) for (auto& e : t.e) e.u = 0;
    }
    void history(uint64_t pc, int kind, bool taken, uint64_t target) override {
        // Direction bits for conditionals; two target bits for other branches.
        if (kind == K_COND) push(taken);
        else { push(((target >> shift) ^ (pc >> shift)) & 1); push(((target >> (shift + 1)) ^ (pc >> (shift + 2))) & 1); }
    }
    void push(bool b) { h.push(b); for (auto& t : tabs) { t.fi.update(h); t.ft.update(h); } }
    Storage storage() const override {
        Storage s; s.add("base", base_entries * (target_bits + 2));
        uint64_t b = 0; for (auto& t : tabs) b += t.entries * (t.tag_bits + target_bits + 2 + 1);
        s.add("tagged", b); s.add("history", h.length()); return s;
    }
    Json stats() const override {
        Json j = Json::object(); Json p = Json::array(); for (auto x : provider_count) p.push(x);
        j["provider"] = p; j["base_provider"] = base_used; j["allocations"] = allocs; return j;
    }
};

inline std::unique_ptr<Indirect> make_indirect(const Config& c) {
    std::string m = c.choice("model", "btb", {"btb", "ittage"});
    if (m == "ittage") return std::make_unique<Ittage>(c);
    return std::make_unique<BtbIndirect>();
}

}  // namespace csim
