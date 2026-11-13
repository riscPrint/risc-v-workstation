// Conditional direction predictors. Written from the published descriptions:
//   bimodal / gshare (McFarling 1993), two-level local and tournament
//   (Yeh & Patt 1991; Kessler, Alpha 21264, 1999), perceptron (Jimenez & Lin 2001),
//   hashed perceptron / GEHL (Tarjan & Skadron 2005; Seznec 2005),
//   TAGE (Seznec & Michaud 2006), loop predictor (Seznec, L-TAGE 2007),
//   statistical corrector (Seznec, TAGE-SC-L, CBP 2014/2016).
// Not bit-exact with any reference implementation. See ComponentSims/README.md.
#pragma once
#include "common.h"

namespace csim {

constexpr int MAXT = 40;  // tagged / hashed tables per model

struct DirMeta {
    bool pred = false;
    // TAGE
    int provider = -1, alt = -1; bool prov_pred = false, alt_pred = false, base_pred = false, used_alt = false, tage_pred = false;
    bool weak_new = false; int conf = 0;  // 0 low, 1 medium, 2 high
    uint32_t base_idx = 0; uint32_t idx[MAXT]; uint32_t tag[MAXT];
    // loop
    bool loop_hit = false, loop_valid = false, loop_pred = false; int loop_set = 0, loop_way = -1; uint32_t loop_tag = 0;
    bool inter_pred = false;
    // SC / perceptron / GEHL
    int sum = 0; bool sc_used = false; uint32_t sidx[MAXT]; int nsidx = 0;
    // local / tournament
    uint32_t local_idx = 0, global_idx = 0, choice_idx = 0; bool local_pred = false, global_pred = false;
    uint64_t hpos = 0;  // history pushes seen at predict time
};

class Direction {
public:
    virtual ~Direction() = default;
    virtual std::string name() const = 0;
    // Predict the conditional branch at pc. Fills m (m.pred is the prediction).
    virtual void predict(uint64_t pc, DirMeta& m) = 0;
    // Train with the actual outcome, using the metadata captured by predict().
    virtual void update(uint64_t pc, bool taken, const DirMeta& m) = 0;
    // Advance histories for any branch on the actual path (called right after predict
    // for conditionals, and once for every other branch).
    virtual void history(uint64_t pc, int kind, bool taken, uint64_t target) { (void)pc; (void)kind; (void)taken; (void)target; }
    virtual Storage storage() const = 0;
    virtual Json stats() const { return Json::object(); }
    // Called before predict() with the actual outcome and target. Only the perfect
    // model (outcome) and the static BTFN rule (decoded target) read it.
    virtual void oracle(bool taken, uint64_t target) { (void)taken; (void)target; }
};

// ------------------------------------------------------------------ simple tables
class Bimodal : public Direction {
protected:
    std::vector<int8_t> t; unsigned bits, shift; uint64_t entries;
public:
    explicit Bimodal(const Config& c)
        : bits(unsigned(c.u("ctr_bits", 2, 1, 7))), shift(unsigned(c.u("pc_shift", 1, 0, 63))), entries(c.u("entries", 4096, 1, 1u << 26)) {
        if (!pow2(entries)) throw Error("bimodal entries must be a power of two");
        t.assign(entries, int8_t((1 << (bits - 1)) - 1));  // weakly not taken
    }
    std::string name() const override { return "bimodal"; }
    void predict(uint64_t pc, DirMeta& m) override { m.base_idx = uint32_t((pc >> shift) & (entries - 1)); m.pred = t[m.base_idx] >= (1 << (bits - 1)); }
    void update(uint64_t, bool taken, const DirMeta& m) override { sat_update(t[m.base_idx], taken, 0, (1 << bits) - 1); }
    Storage storage() const override { Storage s; s.add("counters", entries * bits); return s; }
};

class Gshare : public Direction {
    std::vector<int8_t> t; unsigned shift, hbits; uint64_t entries, hist = 0;
public:
    explicit Gshare(const Config& c)
        : shift(unsigned(c.u("pc_shift", 1, 0, 63))), hbits(unsigned(c.u("history", 12, 0, 63))), entries(c.u("entries", 4096, 1, 1u << 26)) {
        if (!pow2(entries)) throw Error("gshare entries must be a power of two");
        t.assign(entries, 1);
    }
    std::string name() const override { return "gshare"; }
    void predict(uint64_t pc, DirMeta& m) override { m.base_idx = uint32_t(((pc >> shift) ^ hist) & (entries - 1)); m.pred = t[m.base_idx] >= 2; }
    void update(uint64_t, bool taken, const DirMeta& m) override { sat_update(t[m.base_idx], taken, 0, 3); }
    void history(uint64_t, int kind, bool taken, uint64_t) override { if (kind == K_COND) hist = ((hist << 1) | taken) & mask(hbits); }
    Storage storage() const override { Storage s; s.add("counters", entries * 2); s.add("history", hbits); return s; }
};

class Perfect : public Direction {
    bool next = false;
public:
    std::string name() const override { return "perfect"; }
    void oracle(bool taken, uint64_t) override { next = taken; }
    void predict(uint64_t, DirMeta& m) override { m.pred = next; }
    void update(uint64_t, bool, const DirMeta&) override {}
    Storage storage() const override { return Storage(); }
};

class Static : public Direction {
    bool btfn; uint64_t tgt = 0;
public:
    explicit Static(bool backward) : btfn(backward) {}
    std::string name() const override { return btfn ? "btfn" : "always-taken"; }
    void oracle(bool, uint64_t t) override { tgt = t; }
    void predict(uint64_t pc, DirMeta& m) override { m.pred = btfn ? (tgt && tgt < pc) : true; }
    void update(uint64_t, bool, const DirMeta&) override {}
    Storage storage() const override { return Storage(); }
};

// Two-level local predictor and the Alpha-21264-style tournament.
class Tournament : public Direction {
    bool local_only;
    unsigned shift, lbits, gbits, lctr;
    uint64_t lhist_entries;
    std::vector<uint64_t> lhist; std::vector<int8_t> lpht, gpht, choice;
    uint64_t ghist = 0;
    uint64_t chose_local = 0, chose_global = 0;
public:
    Tournament(const Config& c, bool local)
        : local_only(local), shift(unsigned(c.u("pc_shift", 1, 0, 63))), lbits(unsigned(c.u("local_bits", 10, 1, 24))),
          gbits(local ? 0 : unsigned(c.u("global_bits", 12, 1, 24))), lctr(unsigned(c.u("local_ctr_bits", 3, 1, 7))),
          lhist_entries(c.u("local_histories", 1024, 1, 1u << 24)) {
        if (!pow2(lhist_entries)) throw Error("local_histories must be a power of two");
        lhist.assign(lhist_entries, 0); lpht.assign(uint64_t(1) << lbits, int8_t((1 << (lctr - 1)) - 1));
        if (!local_only) { gpht.assign(uint64_t(1) << gbits, 1); choice.assign(uint64_t(1) << gbits, 1); }
    }
    std::string name() const override { return local_only ? "local" : "tournament"; }
    void predict(uint64_t pc, DirMeta& m) override {
        uint64_t li = (pc >> shift) & (lhist_entries - 1);
        m.base_idx = uint32_t(li);
        m.local_idx = uint32_t(lhist[li] & mask(lbits));
        m.local_pred = lpht[m.local_idx] >= (1 << (lctr - 1));
        if (local_only) { m.pred = m.local_pred; return; }
        m.global_idx = uint32_t(ghist & mask(gbits));
        m.global_pred = gpht[m.global_idx] >= 2;
        m.choice_idx = m.global_idx;
        m.pred = choice[m.choice_idx] >= 2 ? m.global_pred : m.local_pred;
        (choice[m.choice_idx] >= 2 ? chose_global : chose_local)++;
    }
    void update(uint64_t, bool taken, const DirMeta& m) override {
        sat_update(lpht[m.local_idx], taken, 0, (1 << lctr) - 1);
        lhist[m.base_idx] = ((lhist[m.base_idx] << 1) | taken) & mask(lbits);
        if (local_only) return;
        if (m.local_pred != m.global_pred) sat_update(choice[m.choice_idx], m.global_pred == taken, 0, 3);
        sat_update(gpht[m.global_idx], taken, 0, 3);
    }
    void history(uint64_t, int kind, bool taken, uint64_t) override { if (kind == K_COND && !local_only) ghist = ((ghist << 1) | taken) & mask(gbits); }
    Storage storage() const override {
        Storage s; s.add("local_histories", lhist_entries * lbits); s.add("local_pht", (uint64_t(1) << lbits) * lctr);
        if (!local_only) { s.add("global_pht", (uint64_t(1) << gbits) * 2); s.add("chooser", (uint64_t(1) << gbits) * 2); s.add("global_history", gbits); }
        return s;
    }
    Json stats() const override { Json j = Json::object(); if (!local_only) { j["chose_local"] = chose_local; j["chose_global"] = chose_global; } return j; }
};

// Global perceptron predictor.
class Perceptron : public Direction {
    unsigned shift, hlen, wbits; uint64_t entries; int theta;
    std::vector<int16_t> w; History h; uint64_t pushes = 0;
    uint64_t trained = 0;
public:
    explicit Perceptron(const Config& c)
        : shift(unsigned(c.u("pc_shift", 1, 0, 63))), hlen(unsigned(c.u("history", 32, 1, 1024))), wbits(unsigned(c.u("weight_bits", 8, 2, 15))),
          entries(c.u("entries", 256, 1, 1u << 20)), h(hlen + 4096) {
        theta = int(c.u("threshold", uint64_t(std::floor(1.93 * hlen + 14)), 0, 1u << 20));
        w.assign(entries * (hlen + 1), 0);
    }
    std::string name() const override { return "perceptron"; }
    void predict(uint64_t pc, DirMeta& m) override {
        m.base_idx = uint32_t((pc >> shift) % entries);
        const int16_t* row = &w[size_t(m.base_idx) * (hlen + 1)];
        int y = row[0];
        for (unsigned i = 0; i < hlen; ++i) y += h.bit(i) ? row[i + 1] : -row[i + 1];
        m.sum = y; m.pred = y >= 0; m.hpos = pushes;
    }
    void update(uint64_t, bool taken, const DirMeta& m) override {
        if (m.pred == taken && std::abs(m.sum) > theta) return;
        uint64_t off = pushes - m.hpos;  // bits pushed since predict (delayed update)
        if (off > 4096) throw Error("perceptron update delay exceeds history buffer");
        ++trained;
        int16_t* row = &w[size_t(m.base_idx) * (hlen + 1)];
        int lo = smin(wbits), hi = smax(wbits);
        sat_update(row[0], taken, lo, hi);
        for (unsigned i = 0; i < hlen; ++i) sat_update(row[i + 1], h.bit(i + off) == taken, lo, hi);
    }
    void history(uint64_t, int kind, bool taken, uint64_t) override { if (kind == K_COND) { h.push(taken); ++pushes; } }
    Storage storage() const override { Storage s; s.add("weights", entries * (hlen + 1) * wbits); s.add("history", hlen); return s; }
    Json stats() const override { Json j = Json::object(); j["threshold"] = theta; j["trained"] = trained; return j; }
};

// Hashed perceptron / GEHL: several weight tables, each indexed by a hash of the PC
// and one global-history interval, summed. Adaptive threshold (O-GEHL rule).
class HashedPerceptron : public Direction {
    struct T { uint64_t entries; unsigned lo, hi; Folded fa, fb; std::vector<int8_t> w; };
    std::vector<T> tabs; unsigned shift, wbits; bool segments; History h; int theta, tc = 0; uint64_t trained = 0;
public:
    explicit HashedPerceptron(const Config& c)
        : shift(unsigned(c.u("pc_shift", 1, 0, 63))), wbits(unsigned(c.u("weight_bits", 6, 2, 8))) {
        segments = c.choice("intervals", "prefix", {"prefix", "segment"}) == "segment";
        size_t n = c.list("tables");
        std::vector<std::pair<uint64_t, unsigned>> spec;
        if (n == 0) {
            unsigned hist[] = {0, 3, 5, 8, 12, 19, 31, 49, 75, 125, 200, 320};
            for (unsigned x : hist) spec.emplace_back(2048, x);
        }
        for (size_t i = 0; i < n; ++i) { auto t = c.at("tables", i); spec.emplace_back(t.u("entries", 2048, 1, 1u << 24), unsigned(t.u("history", 0, 0, 4096))); }
        if (spec.size() > MAXT) throw Error("too many hashed perceptron tables");
        unsigned maxh = 1, prev = 0;
        for (auto& s : spec) {
            if (!pow2(s.first)) throw Error("table entries must be a power of two");
            if (s.second < prev) throw Error("table history lengths must not decrease");
            T t; t.entries = s.first; t.hi = s.second; t.lo = segments ? prev : 0;
            unsigned wdt = log2u(s.first);
            t.fa = Folded(t.hi, wdt); t.fb = Folded(t.lo, wdt);
            t.w.assign(s.first, 0); tabs.push_back(std::move(t));
            prev = s.second; maxh = std::max(maxh, s.second);
        }
        h = History(maxh + 1);
        theta = int(c.u("threshold", tabs.size(), 0, 1u << 16));
    }
    std::string name() const override { return "hashed-perceptron"; }
    void predict(uint64_t pc, DirMeta& m) override {
        uint64_t p = pc >> shift; int y = 0; m.nsidx = int(tabs.size());
        for (size_t i = 0; i < tabs.size(); ++i) {
            auto& t = tabs[i];
            uint64_t f = t.fa.comp ^ (t.lo ? t.fb.comp : 0);
            uint64_t idx = (p ^ (p >> (i + 2)) ^ f ^ (uint64_t(i) * 0x9e37)) & (t.entries - 1);
            m.sidx[i] = uint32_t(idx);
            y += 2 * t.w[idx] + 1;
        }
        m.sum = y; m.pred = y >= 0;
    }
    void update(uint64_t, bool taken, const DirMeta& m) override {
        bool wrong = m.pred != taken;
        if (!wrong && std::abs(m.sum) > theta) return;
        // Adaptive threshold: balance mispredictions against low-confidence updates.
        if (wrong) { if (++tc >= 7) { ++theta; tc = 0; } }
        else { if (--tc <= -7) { if (theta > 0) --theta; tc = 0; } }
        ++trained;
        for (size_t i = 0; i < tabs.size(); ++i) sat_update(tabs[i].w[m.sidx[i]], taken, smin(wbits), smax(wbits));
    }
    void history(uint64_t, int kind, bool taken, uint64_t) override {
        if (kind != K_COND) return;
        h.push(taken);
        for (auto& t : tabs) { t.fa.update(h); t.fb.update(h); }
    }
    Storage storage() const override {
        Storage s; uint64_t b = 0; for (auto& t : tabs) b += t.entries * wbits;
        s.add("weights", b); s.add("history", h.length()); return s;
    }
    Json stats() const override { Json j = Json::object(); j["threshold"] = theta; j["trained"] = trained; j["tables"] = uint64_t(tabs.size()); return j; }
};

// ------------------------------------------------------------------ TAGE-SC-L
class Tage : public Direction {
    struct Entry { int8_t ctr = 0; uint32_t tag = 0; uint8_t u = 0; };
    struct Table { uint64_t entries; unsigned log, tag_bits, hist; std::vector<Entry> e; Folded fi, ft0, ft1; };
    std::vector<Table> tabs;
    std::vector<int8_t> base; uint64_t base_entries; unsigned base_bits;
    unsigned shift, ctr_bits, u_bits, max_alloc, path_bits;
    bool history_all;
    uint64_t u_period, updates = 0;
    int use_alt = 0; unsigned use_alt_bits = 4;
    History h; uint64_t path = 0; Rng rng;
    std::string label;
    // stats
    std::vector<uint64_t> provider_count; uint64_t base_provider = 0, alt_used = 0, allocs = 0, alloc_fail = 0, u_resets = 0;

    // --- loop predictor
    struct LoopEntry { uint32_t tag = 0, past = 0, cur = 0; uint8_t conf = 0, age = 0; bool dir = false; };
    bool use_loop = false; uint64_t loop_sets = 0; unsigned loop_ways = 0, loop_tag_bits = 0, loop_iter_bits = 0, loop_conf_max = 0, loop_age_max = 0;
    std::vector<LoopEntry> loop; int with_loop = -1; uint64_t loop_used = 0, loop_correct = 0, loop_allocs = 0;

    // --- statistical corrector
    struct ScTable { uint64_t entries; unsigned hist; bool local; Folded f; std::vector<int8_t> c; };
    bool use_sc = false; std::vector<ScTable> sc; unsigned sc_bits = 6; int sc_thr = 0, sc_tc = 0;
    uint64_t sc_bias_entries = 0; std::vector<int8_t> sc_bias;
    uint64_t lh_entries = 0; unsigned lh_bits = 0; std::vector<uint64_t> lhist;
    uint64_t sc_override = 0, sc_override_good = 0;

    uint32_t index(const Table& t, size_t i, uint64_t p) const {
        uint64_t ph = path & mask(std::min(path_bits, t.hist));
        uint64_t x = p ^ (p >> (t.log > i ? t.log - i : 1)) ^ t.fi.comp ^ (mix64(ph + i) & mask(t.log));
        return uint32_t(x & (t.entries - 1));
    }
    uint32_t tagof(const Table& t, uint64_t p) const { return uint32_t((p ^ t.ft0.comp ^ (t.ft1.comp << 1)) & mask(t.tag_bits)); }
    int ctr_max() const { return smax(ctr_bits); }
    int ctr_min() const { return smin(ctr_bits); }

public:
    Tage(const Config& c, const std::string& model) : rng(c.u("seed", 1, 1)) {
        label = model;
        shift = unsigned(c.u("pc_shift", 1, 0, 63));
        ctr_bits = unsigned(c.u("ctr_bits", 3, 2, 7));
        u_bits = unsigned(c.u("u_bits", 2, 1, 4));
        max_alloc = unsigned(c.u("max_alloc", 1, 1, 8));
        path_bits = unsigned(c.u("path_bits", 16, 0, 64));
        history_all = c.flag("history_all_branches", false);
        u_period = c.u("u_reset_period", 256 * 1024, 0);
        base_entries = c.u("base_entries", 8192, 1, 1u << 26); base_bits = unsigned(c.u("base_ctr_bits", 2, 1, 7));
        if (!pow2(base_entries)) throw Error("tage base_entries must be a power of two");
        base.assign(base_entries, int8_t((1 << (base_bits - 1)) - 1));
        size_t n = c.list("tables");
        struct Spec { uint64_t entries; unsigned hist, tag; };
        std::vector<Spec> spec;
        if (n == 0) {
            unsigned nt = unsigned(c.u("num_tables", 12, 1, MAXT));
            double lo = double(c.u("min_history", 4, 1, 4096)), hi = double(c.u("max_history", 640, 1, 4096));
            uint64_t ent = c.u("table_entries", 2048, 1, 1u << 24);
            unsigned tag_lo = unsigned(c.u("min_tag_bits", 8, 1, 24)), tag_hi = unsigned(c.u("max_tag_bits", 15, 1, 24));
            for (unsigned i = 0; i < nt; ++i) {
                double frac = nt > 1 ? double(i) / (nt - 1) : 0.0;
                unsigned hl = unsigned(std::lround(lo * std::pow(hi / lo, frac)));
                unsigned tg = tag_lo + unsigned(std::lround((tag_hi - tag_lo) * frac));
                spec.push_back({ent, hl, tg});
            }
        }
        for (size_t i = 0; i < n; ++i) {
            auto t = c.at("tables", i);
            spec.push_back({t.u("entries", 1024, 1, 1u << 24), unsigned(t.u("history", 0, 1, 4096)), unsigned(t.u("tag_bits", 8, 1, 24))});
        }
        if (spec.size() > MAXT) throw Error("too many TAGE tables");
        unsigned maxh = 1, prev = 0;
        for (auto& s : spec) {
            if (!pow2(s.entries)) throw Error("tage table entries must be a power of two");
            if (s.hist < prev) throw Error("tage history lengths must not decrease");
            prev = s.hist;
            Table t; t.entries = s.entries; t.log = log2u(s.entries); t.tag_bits = s.tag; t.hist = s.hist;
            t.e.assign(s.entries, Entry());
            t.fi = Folded(s.hist, t.log); t.ft0 = Folded(s.hist, s.tag); t.ft1 = Folded(s.hist, s.tag > 1 ? s.tag - 1 : 1);
            tabs.push_back(std::move(t)); maxh = std::max(maxh, s.hist);
        }
        provider_count.assign(tabs.size(), 0);

        bool want_loop = model == "tage-sc-l" || model == "ltage";
        bool want_sc = model == "tage-sc-l";
        auto lc = c.at("loop"), scc = c.at("sc");
        use_loop = lc.flag("enabled", want_loop);
        use_sc = scc.flag("enabled", want_sc);
        if (use_loop) {
            uint64_t entries = lc.u("entries", 64, 1, 1u << 16);
            loop_ways = unsigned(lc.u("ways", 4, 1, 64));
            if (entries % loop_ways || !pow2(entries / loop_ways)) throw Error("loop entries/ways must give a power-of-two set count");
            loop_sets = entries / loop_ways;
            loop_tag_bits = unsigned(lc.u("tag_bits", 14, 1, 32));
            loop_iter_bits = unsigned(lc.u("iter_bits", 14, 2, 32));
            loop_conf_max = unsigned(mask(unsigned(lc.u("conf_bits", 2, 1, 4))));
            loop_age_max = unsigned(mask(unsigned(lc.u("age_bits", 8, 1, 8))));
            loop.assign(entries, LoopEntry());
        } else if (lc.any()) lc.flag("enabled", false);
        unsigned max_local = 0;
        if (use_sc) {
            sc_bits = unsigned(scc.u("ctr_bits", 6, 2, 8));
            sc_thr = int(scc.u("threshold", 35, 0, 4096));
            sc_bias_entries = scc.u("bias_entries", 2048, 1, 1u << 22);
            if (!pow2(sc_bias_entries)) throw Error("sc bias_entries must be a power of two");
            sc_bias.assign(sc_bias_entries * 2, 0);
            lh_entries = scc.u("local_histories", 256, 1, 1u << 20);
            if (!pow2(lh_entries)) throw Error("sc local_histories must be a power of two");
            auto add = [&](const Config& tc, bool local, uint64_t ent, unsigned hist) {
                ScTable t; t.entries = tc.u("entries", ent, 1, 1u << 22); t.hist = unsigned(tc.u("history", hist, 0, local ? 64 : 4096)); t.local = local;
                if (!pow2(t.entries)) throw Error("sc table entries must be a power of two");
                t.f = Folded(t.hist, log2u(t.entries)); t.c.assign(t.entries, 0);
                if (local) max_local = std::max(max_local, t.hist); else maxh = std::max(maxh, t.hist);
                sc.push_back(std::move(t));
            };
            size_t ng = scc.list("global"), nl = scc.list("local");
            if (!ng) { unsigned g[] = {0, 11, 22, 33}; for (unsigned x : g) add(scc.at("unused_default_global"), false, 1024, x); }
            for (size_t i = 0; i < ng; ++i) add(scc.at("global", i), false, 1024, 8);
            if (!nl) { unsigned l[] = {0, 4, 10, 16}; for (unsigned x : l) add(scc.at("unused_default_local"), true, 512, x); }
            for (size_t i = 0; i < nl; ++i) add(scc.at("local", i), true, 512, 8);
            if (sc.size() > MAXT) throw Error("too many SC tables");
            lh_bits = std::max(1u, max_local);
            lhist.assign(lh_entries, 0);
        } else if (scc.any()) scc.flag("enabled", false);
        h = History(maxh + 1);
    }

    std::string name() const override { return label; }

    void predict(uint64_t pc, DirMeta& m) override {
        uint64_t p = pc >> shift;
        m.base_idx = uint32_t(p & (base_entries - 1));
        m.base_pred = base[m.base_idx] >= (1 << (base_bits - 1));
        m.provider = m.alt = -1;
        for (size_t i = 0; i < tabs.size(); ++i) { m.idx[i] = index(tabs[i], i, p); m.tag[i] = tagof(tabs[i], p); }
        for (int i = int(tabs.size()) - 1; i >= 0; --i) {
            if (tabs[i].e[m.idx[i]].tag == m.tag[i]) { if (m.provider < 0) m.provider = i; else { m.alt = i; break; } }
        }
        m.alt_pred = m.alt >= 0 ? tabs[m.alt].e[m.idx[m.alt]].ctr >= 0 : m.base_pred;
        if (m.provider >= 0) {
            const Entry& e = tabs[m.provider].e[m.idx[m.provider]];
            m.prov_pred = e.ctr >= 0;
            int mag = std::abs(2 * e.ctr + 1);
            m.weak_new = mag == 1 && e.u == 0;
            m.used_alt = m.weak_new && use_alt >= 0;
            m.tage_pred = m.used_alt ? m.alt_pred : m.prov_pred;
            m.conf = mag >= 2 * ctr_max() + 1 ? 2 : mag >= 2 * ctr_max() - 1 ? 1 : 0;
        } else {
            m.prov_pred = m.base_pred; m.used_alt = false; m.weak_new = false; m.tage_pred = m.base_pred;
            int b = base[m.base_idx]; m.conf = (b == 0 || b == (1 << base_bits) - 1) ? 2 : 0;
        }
        m.pred = m.inter_pred = m.tage_pred;
        if (use_loop) {
            m.loop_set = int(p & (loop_sets - 1));
            m.loop_tag = uint32_t((p >> log2u(loop_sets)) & mask(loop_tag_bits));
            m.loop_way = -1; m.loop_hit = m.loop_valid = false;
            for (unsigned w = 0; w < loop_ways; ++w) {
                const LoopEntry& e = loop[size_t(m.loop_set) * loop_ways + w];
                if (e.tag == m.loop_tag && (e.past || e.cur || e.conf || e.age)) {
                    m.loop_way = int(w); m.loop_hit = true;
                    m.loop_valid = e.conf == loop_conf_max && e.past > 0;
                    m.loop_pred = (e.cur + 1 == e.past) ? !e.dir : e.dir;
                    break;
                }
            }
            if (m.loop_valid && with_loop >= 0) m.inter_pred = m.loop_pred;
            m.pred = m.inter_pred;
        }
        if (use_sc) {
            uint64_t lh = lhist[p & (lh_entries - 1)];
            int sum = 0; m.nsidx = int(sc.size());
            uint64_t bidx = ((p ^ (uint64_t(m.conf) << 3)) & (sc_bias_entries - 1)) * 2 + m.inter_pred;
            sum += 2 * sc_bias[bidx] + 1;
            for (size_t i = 0; i < sc.size(); ++i) {
                auto& t = sc[i];
                uint64_t hv = t.local ? (lh & mask(t.hist)) : t.f.comp;
                uint64_t x = mix64((p << 1) ^ m.inter_pred ^ (uint64_t(i) << 56)) ^ (t.local ? mix64(hv + 0x51) : hv);
                m.sidx[i] = uint32_t(x & (t.entries - 1));
                sum += 2 * t.c[m.sidx[i]] + 1;
            }
            // The TAGE/loop input enters the sum through the bias tables, indexed by
            // its direction and confidence.
            m.sum = sum;
            bool scp = sum >= 0;
            m.sc_used = scp != m.inter_pred && std::abs(sum) >= sc_thr;
            if (m.sc_used) m.pred = scp;
        }
    }

    void update(uint64_t pc, bool taken, const DirMeta& m) override {
        uint64_t p = pc >> shift;
        ++updates;
        // --- loop
        if (use_loop) update_loop(m, taken);
        // --- SC
        if (use_sc) {
            bool scp = m.sum >= 0;
            if (scp != m.inter_pred) {
                if (m.sc_used) { ++sc_override; sc_override_good += scp == taken; }
                if (scp == taken) { if (--sc_tc < -32) { if (sc_thr > 4) --sc_thr; sc_tc = 0; } }
                else { if (++sc_tc > 31) { ++sc_thr; sc_tc = 0; } }
            }
            if (scp != taken || std::abs(m.sum) < sc_thr) {
                uint64_t bidx = ((p ^ (uint64_t(m.conf) << 3)) & (sc_bias_entries - 1)) * 2 + m.inter_pred;
                sat_update(sc_bias[bidx], taken, smin(sc_bits), smax(sc_bits));
                for (size_t i = 0; i < sc.size(); ++i) sat_update(sc[i].c[m.sidx[i]], taken, smin(sc_bits), smax(sc_bits));
            }
            uint64_t& l = lhist[p & (lh_entries - 1)];
            l = ((l << 1) | taken) & mask(lh_bits);
        }
        // --- TAGE
        if (m.provider >= 0) provider_count[m.provider]++; else base_provider++;
        if (m.used_alt) alt_used++;
        if (m.provider >= 0 && m.weak_new && m.prov_pred != m.alt_pred)
            sat_update(use_alt, m.alt_pred == taken, -(1 << (use_alt_bits - 1)), (1 << (use_alt_bits - 1)) - 1);
        bool alloc = m.tage_pred != taken && m.provider < int(tabs.size()) - 1;
        if (m.provider >= 0 && m.used_alt && m.prov_pred == taken) alloc = false;
        if (alloc) {
            int start = m.provider + 1;
            if (start + 1 < int(tabs.size()) && (rng.next() & 1)) ++start;  // random skip, spreads allocations
            unsigned done = 0;
            for (int i = start; i < int(tabs.size()) && done < max_alloc; ++i) {
                Entry& e = tabs[i].e[m.idx[i]];
                if (e.u == 0) { e.tag = m.tag[i]; e.ctr = taken ? 0 : -1; e.u = 0; ++done; ++allocs; }
            }
            if (!done) {
                ++alloc_fail;
                for (int i = start; i < int(tabs.size()); ++i) { Entry& e = tabs[i].e[m.idx[i]]; if (e.u) --e.u; }
            }
        }
        if (m.provider >= 0) {
            Entry& e = tabs[m.provider].e[m.idx[m.provider]];
            sat_update(e.ctr, taken, ctr_min(), ctr_max());
            if (e.u == 0 || m.weak_new) {  // fresh entry: also train the alternate
                if (m.alt >= 0) sat_update(tabs[m.alt].e[m.idx[m.alt]].ctr, taken, ctr_min(), ctr_max());
                else sat_update(base[m.base_idx], taken, 0, (1 << base_bits) - 1);
            }
            if (m.prov_pred != m.alt_pred) sat_update(e.u, m.prov_pred == taken, 0, int(mask(u_bits)));
        } else {
            sat_update(base[m.base_idx], taken, 0, (1 << base_bits) - 1);
        }
        if (u_period && updates % u_period == 0) {  // graceful aging of useful bits
            ++u_resets;
            for (auto& t : tabs) for (auto& e : t.e) e.u >>= 1;
        }
    }

    void update_loop(const DirMeta& m, bool taken) {
        if (m.loop_valid && m.loop_pred != m.tage_pred) sat_update(with_loop, m.loop_pred == taken, -64, 63);
        if (m.loop_valid && with_loop >= 0) { ++loop_used; loop_correct += m.loop_pred == taken; }
        auto* set = &loop[size_t(m.loop_set) * loop_ways];
        if (m.loop_hit) {
            LoopEntry& e = set[m.loop_way];
            if (m.loop_valid && m.loop_pred != taken) { e = LoopEntry(); return; }  // wrong confident loop: free
            if (m.loop_valid && m.loop_pred == taken && m.tage_pred != taken && e.age < loop_age_max) ++e.age;
            e.cur = uint32_t((e.cur + 1) & mask(loop_iter_bits));
            if (e.cur == 0) { e = LoopEntry(); return; }  // iteration overflow
            if (taken != e.dir) {  // loop exit
                if (e.cur == e.past) { if (e.conf < loop_conf_max) ++e.conf; }
                else if (e.past == 0) { e.past = e.cur; }
                else { e.past = e.cur; e.conf = 0; }
                e.cur = 0;
            }
            return;
        }
        if (m.pred == taken) return;  // allocate only on a final misprediction
        int victim = -1;
        for (unsigned w = 0; w < loop_ways; ++w) if (set[w].age == 0) { victim = int(w); break; }
        if (victim < 0) { for (unsigned w = 0; w < loop_ways; ++w) --set[w].age; return; }
        LoopEntry& e = set[victim];
        e = LoopEntry(); e.tag = m.loop_tag; e.dir = !taken; e.age = uint8_t(loop_age_max); e.cur = 0;
        // The current execution is the exit (direction !dir); count starts on the next instance.
        ++loop_allocs;
    }

    void history(uint64_t pc, int kind, bool taken, uint64_t target) override {
        if (kind != K_COND && !history_all) return;
        bool bit = kind == K_COND ? taken : bool(((pc >> shift) ^ (target >> shift)) & 1);
        h.push(bit);
        path = (path << 1) | ((pc >> shift) & 1);
        for (auto& t : tabs) { t.fi.update(h); t.ft0.update(h); t.ft1.update(h); }
        for (auto& t : sc) if (!t.local) t.f.update(h);
    }

    Storage storage() const override {
        Storage s;
        s.add("base", base_entries * base_bits);
        uint64_t tagged = 0; for (auto& t : tabs) tagged += t.entries * (ctr_bits + u_bits + t.tag_bits);
        s.add("tagged", tagged);
        s.add("global_history", h.length() + path_bits);
        s.add("use_alt", use_alt_bits);
        if (use_loop) s.add("loop", loop.size() * (loop_tag_bits + 2 * loop_iter_bits + log2u(loop_conf_max + 1) + log2u(loop_age_max + 1) + 1) + 7);
        if (use_sc) {
            uint64_t b = sc_bias.size() * sc_bits; for (auto& t : sc) b += t.entries * sc_bits;
            s.add("sc_tables", b); s.add("sc_local_histories", lh_entries * lh_bits); s.add("sc_threshold", 12 + 7);
        }
        return s;
    }

    Json stats() const override {
        Json j = Json::object();
        Json comps = Json::array(); comps.push("tage"); if (use_loop) comps.push("loop"); if (use_sc) comps.push("sc");
        j["components"] = comps;
        Json tables = Json::array();
        for (size_t i = 0; i < tabs.size(); ++i) {
            Json t = Json::object(); t["entries"] = tabs[i].entries; t["history"] = tabs[i].hist; t["tag_bits"] = tabs[i].tag_bits; t["provider"] = provider_count[i];
            tables.push(t);
        }
        j["tables"] = tables; j["base_provider"] = base_provider; j["alt_used"] = alt_used;
        j["allocations"] = allocs; j["allocation_failures"] = alloc_fail; j["u_aging_events"] = u_resets;
        if (use_loop) { Json l = Json::object(); l["used"] = loop_used; l["correct"] = loop_correct; l["allocations"] = loop_allocs; j["loop"] = l; }
        if (use_sc) { Json l = Json::object(); l["overrides"] = sc_override; l["overrides_correct"] = sc_override_good; l["threshold"] = sc_thr; l["tables"] = uint64_t(sc.size() + 1); j["sc"] = l; }
        return j;
    }
};

inline std::unique_ptr<Direction> make_direction(const Config& c) {
    std::string m = c.choice("model", "bimodal", {"bimodal", "gshare", "perfect", "always-taken", "btfn", "local", "tournament",
                                                  "perceptron", "hashed-perceptron", "tage", "ltage", "tage-sc-l"});
    if (m == "bimodal") return std::make_unique<Bimodal>(c);
    if (m == "gshare") return std::make_unique<Gshare>(c);
    if (m == "perfect") return std::make_unique<Perfect>();
    if (m == "always-taken") return std::make_unique<Static>(false);
    if (m == "btfn") return std::make_unique<Static>(true);
    if (m == "local") return std::make_unique<Tournament>(c, true);
    if (m == "tournament") return std::make_unique<Tournament>(c, false);
    if (m == "perceptron") return std::make_unique<Perceptron>(c);
    if (m == "hashed-perceptron") return std::make_unique<HashedPerceptron>(c);
    return std::make_unique<Tage>(c, m);
}

}  // namespace csim
