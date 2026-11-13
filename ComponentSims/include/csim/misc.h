// Memory-dependence prediction (store sets, Chrysos & Emer ISCA 1998; Alpha 21264
// wait table) and value prediction (last value, stride, VTAGE after Perais & Seznec,
// HPCA 2014), plus move-elimination and zero-idiom counts. Owner-written.
// The dependence model has no timing: every older store inside `unresolved_window`
// instructions is treated as address-unresolved when the load issues.
#pragma once
#include <deque>
#include "common.h"

namespace csim {

class StoreSets {
    struct St { uint64_t ord, pc, addr; uint8_t size; };
    std::string policy; uint64_t window, clear_period, last_clear = 0;
    std::deque<St> stores;
    std::vector<uint32_t> ssit; std::vector<uint8_t> ssit_valid; std::vector<uint64_t> lfst; uint32_t next_id = 0; unsigned ssid_bits;
    std::vector<uint8_t> wait;
    uint64_t loads = 0, nstores = 0, conflicts = 0, violations = 0, false_deps = 0, waits = 0;
    uint64_t ix(uint64_t pc) const { return mix64(pc) & (ssit.size() - 1); }
public:
    explicit StoreSets(const Config& c) {
        policy = c.choice("model", "store-sets", {"store-sets", "wait-table", "always-speculate", "never-speculate", "perfect"});
        window = c.u("unresolved_window", 64, 1, 1u << 20);
        clear_period = c.u("clear_period", 1000000, 0);
        uint64_t n = c.u("ssit_entries", 4096, 1, 1u << 22); if (!pow2(n)) throw Error("ssit_entries must be a power of two");
        uint64_t m = c.u("lfst_entries", 256, 1, 1u << 20); if (!pow2(m)) throw Error("lfst_entries must be a power of two");
        ssid_bits = log2u(m);
        ssit.assign(n, 0); ssit_valid.assign(n, 0); lfst.assign(m, 0); wait.assign(n, 0);
    }
    void tick(uint64_t ord) {
        while (!stores.empty() && stores.front().ord + window <= ord) stores.pop_front();
        if (clear_period && ord - last_clear >= clear_period) {
            last_clear = ord; std::fill(ssit_valid.begin(), ssit_valid.end(), 0); std::fill(wait.begin(), wait.end(), 0);
        }
    }
    void store(uint64_t ord, uint64_t pc, uint64_t addr, uint8_t size, bool measure) {
        tick(ord); if (measure) ++nstores;
        stores.push_back({ord, pc, addr, size});
        uint64_t k = ix(pc); if (ssit_valid[k]) lfst[ssit[k]] = ord;
    }
    void load(uint64_t ord, uint64_t pc, uint64_t addr, uint8_t size, bool measure) {
        tick(ord);
        const St* dep = nullptr;
        for (auto it = stores.rbegin(); it != stores.rend(); ++it)
            if (it->ord < ord && it->addr < addr + size && addr < it->addr + it->size) { dep = &*it; break; }
        bool older = false; for (auto& s : stores) if (s.ord < ord) { older = true; break; }
        bool wait_pred = false, covered = false;
        uint64_t k = ix(pc);
        if (policy == "never-speculate") { wait_pred = older; covered = true; }
        else if (policy == "perfect") { wait_pred = dep != nullptr; covered = true; }
        else if (policy == "wait-table") { wait_pred = wait[k] && older; covered = wait_pred; }
        else if (policy == "store-sets") {
            if (ssit_valid[k]) {
                uint64_t last = lfst[ssit[k]];
                if (last && last < ord && last + window > ord) {
                    wait_pred = true;
                    uint64_t dk = dep ? ix(dep->pc) : 0;
                    covered = dep && ssit_valid[dk] && ssit[dk] == ssit[k] && last >= dep->ord;
                }
            }
        }
        if (measure) { ++loads; if (dep) ++conflicts; if (wait_pred) ++waits; }
        if (dep && !covered) {
            if (measure) ++violations;
            if (policy == "wait-table") wait[k] = 1;
            if (policy == "store-sets") {
                uint64_t sk = ix(dep->pc);
                bool lv = ssit_valid[k], sv = ssit_valid[sk];
                uint32_t id;
                if (!lv && !sv) id = next_id++ & uint32_t(mask(ssid_bits));
                else if (lv && sv) id = std::min(ssit[k], ssit[sk]);
                else id = lv ? ssit[k] : ssit[sk];
                ssit[k] = ssit[sk] = id; ssit_valid[k] = ssit_valid[sk] = 1;
                lfst[id] = dep->ord;
            }
        } else if (!dep && wait_pred && measure) ++false_deps;
    }
    Storage storage() const {
        Storage s;
        if (policy == "store-sets") { s.add("ssit", ssit.size() * (ssid_bits + 1)); s.add("lfst", lfst.size() * 10); }
        if (policy == "wait-table") s.add("wait_table", wait.size());
        return s;
    }
    Json stats(uint64_t instructions) const {
        Json j = Json::object(); j["model"] = policy; j["unresolved_window"] = window;
        j["loads"] = loads; j["stores"] = nstores; j["loads_with_conflict"] = conflicts; j["violations"] = violations;
        j["violations_pki"] = per_kilo(violations, instructions); j["false_dependences"] = false_deps; j["predicted_waits"] = waits;
        j["timing"] = "none: all older stores in the window are unresolved";
        return j;
    }
};

class ValuePredictor {
    struct E { uint64_t tag = 0, value = 0; int64_t stride = 0; uint8_t conf = 0, u = 0; bool valid = false; };
    struct T { uint64_t entries; unsigned hist, tag_bits; std::vector<E> e; Folded f; };
    std::string model; bool loads_only; unsigned conf_max, thr;
    std::vector<E> base; std::vector<T> tabs; History h; unsigned shift = 1;
    uint64_t eligible = 0, predicted = 0, correct = 0, wrong = 0, moves = 0, zeros = 0, writes = 0;
    uint64_t bix(uint64_t pc) const { return (pc >> shift) & (base.size() - 1); }
public:
    explicit ValuePredictor(const Config& c) {
        model = c.choice("model", "last-value", {"last-value", "stride", "vtage"});
        loads_only = c.choice("eligible", "loads", {"loads", "all"}) == "loads";
        unsigned cb = unsigned(c.u("conf_bits", 3, 1, 8)); conf_max = unsigned(mask(cb)); thr = unsigned(c.u("threshold", conf_max, 1, conf_max));
        uint64_t n = c.u("entries", 4096, 1, 1u << 22); if (!pow2(n)) throw Error("value predictor entries must be a power of two");
        base.assign(n, E());
        unsigned maxh = 1;
        if (model == "vtage") {
            size_t nt = c.list("tables");
            std::vector<std::pair<uint64_t, unsigned>> spec;
            if (!nt) { unsigned hs[] = {2, 4, 8, 16, 32, 64}; for (unsigned x : hs) spec.emplace_back(1024, x); }
            for (size_t i = 0; i < nt; ++i) { auto t = c.at("tables", i); spec.emplace_back(t.u("entries", 1024, 1, 1u << 22), unsigned(t.u("history", 8, 1, 1024))); }
            if (spec.size() > 64) throw Error("too many VTAGE tables");
            for (auto& s : spec) {
                if (!pow2(s.first)) throw Error("vtage entries must be a power of two");
                T t; t.entries = s.first; t.hist = s.second; t.tag_bits = 12; t.e.assign(s.first, E()); t.f = Folded(s.second, log2u(s.first));
                tabs.push_back(std::move(t)); maxh = std::max(maxh, s.second);
            }
        }
        h = History(maxh + 1);
    }
    void branch(int kind, bool taken) { if (kind != K_COND) return; h.push(taken); for (auto& t : tabs) t.f.update(h); }
    void value(uint64_t pc, uint64_t v, bool is_load, bool is_move, bool is_zero, bool measure) {
        if (measure) { ++writes; moves += is_move; zeros += is_zero; }
        if (loads_only && !is_load) return;
        if (measure) ++eligible;
        uint64_t p = pc >> shift;
        E& b = base[bix(pc)];
        bool hitb = b.valid && b.tag == pc;
        // Find prediction.
        int prov = -1; uint64_t idx[64]; uint64_t tg[64];
        for (size_t i = 0; i < tabs.size(); ++i) {
            idx[i] = (p ^ (p >> 7) ^ tabs[i].f.comp ^ (i * 0x3c1)) & (tabs[i].entries - 1);
            tg[i] = (mix64(p) ^ tabs[i].f.comp) & mask(tabs[i].tag_bits);
        }
        for (int i = int(tabs.size()) - 1; i >= 0; --i) if (tabs[i].e[idx[i]].valid && tabs[i].e[idx[i]].tag == tg[i]) { prov = i; break; }
        E* src = prov >= 0 ? &tabs[prov].e[idx[prov]] : (hitb ? &b : nullptr);
        bool have = src && src->conf >= thr;
        uint64_t guess = src ? (model == "stride" ? src->value + uint64_t(src->stride) : src->value) : 0;
        if (have && measure) { ++predicted; if (guess == v) ++correct; else ++wrong; }
        // Update.
        auto train = [&](E& e) {
            uint64_t g = model == "stride" ? e.value + uint64_t(e.stride) : e.value;
            if (g == v) { if (e.conf < conf_max) ++e.conf; }
            else { e.conf = 0; }
            if (model == "stride") e.stride = int64_t(v - e.value);
            e.value = v;
        };
        if (!hitb) { b = E(); b.valid = true; b.tag = pc; b.value = v; }
        else if (prov < 0) train(b);
        if (prov >= 0) {
            E& e = tabs[prov].e[idx[prov]];
            bool ok = e.value == v; train(e); if (ok && e.u < 3) ++e.u;
        }
        bool src_ok = src && guess == v;
        if (!src_ok && model == "vtage") {
            bool done = false;
            for (size_t i = size_t(prov + 1); i < tabs.size(); ++i) {
                E& e = tabs[i].e[idx[i]];
                if (!e.valid || e.u == 0) { e = E(); e.valid = true; e.tag = tg[i]; e.value = v; done = true; break; }
            }
            if (!done) for (size_t i = size_t(prov + 1); i < tabs.size(); ++i) { E& e = tabs[i].e[idx[i]]; if (e.u) --e.u; }
        }
    }
    Storage storage() const {
        Storage s; s.add("base", base.size() * (64 + 16 + 3 + (model == "stride" ? 64 : 0)));
        uint64_t t = 0; for (auto& x : tabs) t += x.entries * (64 + 12 + 3 + 2); s.add("tagged", t); return s;
    }
    Json stats(uint64_t instructions) const {
        Json j = Json::object(); j["model"] = model; j["eligible"] = loads_only ? "loads" : "all";
        j["register_writes"] = writes; j["eligible_values"] = eligible; j["predicted"] = predicted; j["correct"] = correct; j["incorrect"] = wrong;
        j["coverage"] = ratio(double(predicted), double(eligible)); j["accuracy"] = ratio(double(correct), double(predicted));
        j["mispredictions_pki"] = per_kilo(wrong, instructions);
        j["move_candidates"] = moves; j["zero_idioms"] = zeros;
        return j;
    }
};


// Load address prediction: last address, stride, or context (a second table indexed
// by the PC and the recent delta history). A prediction is made only at full
// confidence; coverage and accuracy are reported per eligible load.
class AddressPredictor {
    struct E { bool valid = false; uint64_t tag = 0, last = 0; int64_t stride = 0; uint8_t conf = 0; uint32_t hist = 0; };
    struct C { int64_t delta = 0; uint8_t conf = 0; };
    std::string model; std::vector<E> t; std::vector<C> ctx; unsigned conf_max;
    uint64_t loads = 0, predicted = 0, correct = 0, wrong = 0;
public:
    explicit AddressPredictor(const Config& c) {
        model = c.choice("model", "stride", {"last-address", "stride", "context"});
        uint64_t n = c.u("entries", 1024, 1, 1u << 22); if (!pow2(n)) throw Error("address predictor entries must be a power of two");
        t.assign(n, E()); conf_max = unsigned(mask(unsigned(c.u("conf_bits", 2, 1, 8))));
        if (model == "context") { uint64_t m = c.u("context_entries", 4096, 1, 1u << 22); if (!pow2(m)) throw Error("context_entries must be a power of two"); ctx.assign(m, C()); }
    }
    void load(uint64_t pc, uint64_t addr, bool measure) {
        if (measure) ++loads;
        E& e = t[mix64(pc) & (t.size() - 1)];
        if (!e.valid || e.tag != pc) { e = E(); e.valid = true; e.tag = pc; e.last = addr; return; }
        int64_t d = int64_t(addr - e.last);
        uint64_t guess = 0; bool have = false;
        if (model == "last-address") { have = e.conf >= conf_max; guess = e.last; }
        else if (model == "stride") { have = e.conf >= conf_max; guess = e.last + uint64_t(e.stride); }
        else { C& x = ctx[mix64(pc ^ (uint64_t(e.hist) << 40)) & (ctx.size() - 1)]; have = x.conf >= conf_max; guess = e.last + uint64_t(x.delta); }
        if (have && measure) { ++predicted; if (guess == addr) ++correct; else ++wrong; }
        if (model == "last-address") { if (d == 0) { if (e.conf < conf_max) ++e.conf; } else e.conf = 0; }
        else if (model == "stride") { if (d == e.stride) { if (e.conf < conf_max) ++e.conf; } else { e.conf = 0; e.stride = d; } }
        else {
            C& x = ctx[mix64(pc ^ (uint64_t(e.hist) << 40)) & (ctx.size() - 1)];
            if (x.delta == d) { if (x.conf < conf_max) ++x.conf; } else { x.conf = 0; x.delta = d; }
            e.hist = uint32_t(((e.hist << 8) ^ uint32_t(d & 0xff)) & 0xffff);
        }
        e.last = addr;
    }
    Storage storage() const {
        Storage s; s.add("table", t.size() * (16 + 48 + (model == "stride" ? 20 : 0) + log2u(conf_max + 1) + (model == "context" ? 16 : 0)));
        if (!ctx.empty()) s.add("context", ctx.size() * (20 + log2u(conf_max + 1)));
        return s;
    }
    Json stats(uint64_t instructions) const {
        Json j = Json::object(); j["model"] = model; j["loads"] = loads; j["predicted"] = predicted; j["correct"] = correct; j["incorrect"] = wrong;
        j["coverage"] = ratio(double(predicted), double(loads)); j["accuracy"] = ratio(double(correct), double(predicted));
        j["mispredictions_pki"] = per_kilo(wrong, instructions);
        return j;
    }
};

}  // namespace csim
