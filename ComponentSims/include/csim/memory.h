// Cache hierarchy, replacement policies, data/instruction prefetchers and TLBs.
// Written from the published descriptions:
//   tree-PLRU; SRRIP/BRRIP/DRRIP (Jaleel et al., ISCA 2010); SHiP (Wu et al., MICRO 2011);
//   Hawkeye (Jain & Lin, ISCA 2016); Belady OPT (1966);
//   IP-stride (Chen & Baer 1995); stream detector (Palacharla & Kessler 1994 style);
//   BOP (Michaud, HPCA 2016); SPP (Kim et al., MICRO 2016); SMS (Somogyi et al., ISCA 2006);
//   Berti (Navarro-Torres et al., MICRO 2022); EIP (Ros & Jimborean, ISCA 2021).
// Timing is approximate: a request completes at a computed cycle; there is no
// bandwidth model beyond a per-level outstanding-prefetch limit. Owner-written.
#pragma once
#include <deque>
#include <queue>
#include <unordered_map>
#include "common.h"

namespace csim {

struct Line {
    bool valid = false, dirty = false, prefetched = false, by_prefetch = false;
    uint64_t tag = 0;          // full line address
    uint64_t ready = 0;        // cycle the fill completes
    uint64_t stamp = 0;        // LRU stamp
    uint32_t fill_latency = 0;
    uint32_t sig = 0;          // SHiP / Hawkeye PC signature
    bool reused = false;       // SHiP outcome bit
    uint8_t rrpv = 0;
};

struct AccessInfo { uint64_t line = 0, pc = 0, time = 0, next_use = UINT64_MAX; bool prefetch = false, write = false; };

// ------------------------------------------------------------------ replacement
class Replacement {
public:
    unsigned ways = 1; uint64_t sets = 1;
    virtual ~Replacement() = default;
    virtual std::string name() const = 0;
    virtual void init(uint64_t s, unsigned w) { sets = s; ways = w; }
    virtual void access(uint64_t, Line*, const AccessInfo&) {}  // every lookup (before hit/miss handling)
    virtual int victim(uint64_t set, Line* l, const AccessInfo& a) = 0;
    virtual void hit(uint64_t set, int way, Line* l, const AccessInfo& a) = 0;
    virtual void fill(uint64_t set, int way, Line* l, const AccessInfo& a) = 0;
    virtual void evict(uint64_t, int, Line&) {}
    virtual uint64_t bits_per_line() const { return 0; }
    virtual uint64_t extra_bits() const { return 0; }
    virtual Json stats() const { return Json::object(); }
    static int invalid(Line* l, unsigned ways) { for (unsigned w = 0; w < ways; ++w) if (!l[w].valid) return int(w); return -1; }
};

class Lru : public Replacement {
    uint64_t clock = 0;
public:
    std::string name() const override { return "lru"; }
    int victim(uint64_t, Line* l, const AccessInfo&) override {
        int v = invalid(l, ways); if (v >= 0) return v;
        v = 0; for (unsigned w = 1; w < ways; ++w) if (l[w].stamp < l[v].stamp) v = int(w); return v;
    }
    void hit(uint64_t, int w, Line* l, const AccessInfo&) override { l[w].stamp = ++clock; }
    void fill(uint64_t, int w, Line* l, const AccessInfo&) override { l[w].stamp = ++clock; }
    uint64_t bits_per_line() const override { return log2u(ways); }
};

class RandomRepl : public Replacement {
    Rng rng{12345};
public:
    std::string name() const override { return "random"; }
    int victim(uint64_t, Line* l, const AccessInfo&) override { int v = invalid(l, ways); return v >= 0 ? v : int(rng.below(ways)); }
    void hit(uint64_t, int, Line*, const AccessInfo&) override {}
    void fill(uint64_t, int, Line*, const AccessInfo&) override {}
};

class Plru : public Replacement {  // binary tree pseudo-LRU
    std::vector<uint8_t> bits;
public:
    std::string name() const override { return "plru"; }
    void init(uint64_t s, unsigned w) override { if (!pow2(w)) throw Error("plru needs power-of-two ways"); Replacement::init(s, w); bits.assign(s * w, 0); }
    void touch(uint64_t set, int way) {
        uint8_t* b = &bits[set * ways]; unsigned node = 1, lo = 0, hi = ways;
        while (hi - lo > 1) { unsigned mid = (lo + hi) / 2; bool right = unsigned(way) >= mid; b[node] = !right; node = node * 2 + right; if (right) lo = mid; else hi = mid; }
    }
    int victim(uint64_t set, Line* l, const AccessInfo&) override {
        int v = invalid(l, ways); if (v >= 0) return v;
        uint8_t* b = &bits[set * ways]; unsigned node = 1, lo = 0, hi = ways;
        while (hi - lo > 1) { unsigned mid = (lo + hi) / 2; bool right = b[node]; node = node * 2 + right; if (right) lo = mid; else hi = mid; }
        return int(lo);
    }
    void hit(uint64_t set, int w, Line*, const AccessInfo&) override { touch(set, w); }
    void fill(uint64_t set, int w, Line*, const AccessInfo&) override { touch(set, w); }
    uint64_t bits_per_line() const override { return 1; }
};

// RRIP family. mode: 0 SRRIP, 1 BRRIP, 2 DRRIP (set dueling), 3 SHiP (SRRIP + SHCT)
class Rrip : public Replacement {
    int mode; unsigned rbits; int maxr; Rng rng{99};
    unsigned psel = 512, psel_max = 1023, leaders = 32;
    std::vector<uint8_t> shct; unsigned sig_bits = 14; uint64_t brrip_long = 0;
public:
    explicit Rrip(int m, const Config& c) : mode(m) {
        rbits = unsigned(c.u("rrpv_bits", 2, 1, 4)); maxr = (1 << rbits) - 1;
        if (mode == 3) { sig_bits = unsigned(c.u("signature_bits", 14, 4, 20)); shct.assign(size_t(1) << sig_bits, 1); }
        if (mode == 2) leaders = unsigned(c.u("leader_sets", 32, 1, 1024));
    }
    std::string name() const override { const char* n[] = {"srrip", "brrip", "drrip", "ship"}; return n[mode]; }
    int set_kind(uint64_t set) const {  // 0 follower, 1 SRRIP leader, 2 BRRIP leader
        if (mode != 2 || sets < 2 * leaders) return 0;
        uint64_t stride = sets / leaders, r = set % stride;
        return r == 0 ? 1 : r == 1 ? 2 : 0;
    }
    int victim(uint64_t, Line* l, const AccessInfo&) override {
        int v = invalid(l, ways); if (v >= 0) return v;
        while (true) {
            for (unsigned w = 0; w < ways; ++w) if (l[w].rrpv >= maxr) return int(w);
            for (unsigned w = 0; w < ways; ++w) ++l[w].rrpv;
        }
    }
    void hit(uint64_t, int w, Line* l, const AccessInfo& a) override {
        l[w].rrpv = 0;
        if (mode == 3 && !a.prefetch) { l[w].reused = true; uint8_t& c = shct[l[w].sig]; if (c < 7) ++c; }
    }
    bool brrip_insert() { return rng.below(32) != 0; }  // distant most of the time
    void fill(uint64_t set, int w, Line* l, const AccessInfo& a) override {
        uint8_t r = uint8_t(maxr - 1);
        bool distant = false;
        if (mode == 1) distant = brrip_insert();
        else if (mode == 2) {
            int k = set_kind(set);
            bool use_b = k == 2 || (k == 0 && psel > psel_max / 2);
            if (k == 1) { if (psel < psel_max) ++psel; }  // a miss in an SRRIP leader favours BRRIP
            else if (k == 2) { if (psel > 0) --psel; }
            distant = use_b && brrip_insert();
        } else if (mode == 3) {
            l[w].sig = uint32_t(mix64(a.pc ^ (a.prefetch ? 0x5a5a : 0)) & mask(sig_bits)); l[w].reused = false;
            distant = shct[l[w].sig] == 0;
        }
        if (distant) { r = uint8_t(maxr); ++brrip_long; }
        l[w].rrpv = r;
    }
    void evict(uint64_t, int, Line& line) override {
        if (mode == 3 && line.valid && !line.reused) { uint8_t& c = shct[line.sig]; if (c) --c; }
    }
    uint64_t bits_per_line() const override { return rbits + (mode == 3 ? sig_bits + 1 : 0); }
    uint64_t extra_bits() const override { return mode == 2 ? 10 : mode == 3 ? shct.size() * 3 : 0; }
    Json stats() const override { Json j = Json::object(); j["distant_inserts"] = brrip_long; if (mode == 2) j["psel"] = psel; return j; }
};

// Hawkeye: OPTgen on sampled sets trains a PC predictor; insertion as cache-friendly
// (RRPV 0) or cache-averse (RRPV max).
class Hawkeye : public Replacement {
    static constexpr int MAXR = 7;
    unsigned sig_bits = 11, sample_every = 8; std::vector<uint8_t> pred;  // 3-bit counters
    struct Sample { uint64_t line, pc; uint64_t when; };
    struct OptGen { std::vector<uint8_t> occ; uint64_t now = 0; std::unordered_map<uint64_t, std::pair<uint64_t, uint32_t>> last; };
    std::vector<OptGen> gen; size_t window = 0; uint64_t opt_hits = 0, opt_access = 0;
    uint32_t sig(uint64_t pc) const { return uint32_t(mix64(pc) & mask(sig_bits)); }
public:
    explicit Hawkeye(const Config& c) { sig_bits = unsigned(c.u("signature_bits", 11, 4, 20)); sample_every = unsigned(c.u("sample_every", 8, 1, 1024)); pred.assign(size_t(1) << sig_bits, 4); }
    std::string name() const override { return "hawkeye"; }
    void init(uint64_t s, unsigned w) override {
        Replacement::init(s, w); window = 8 * w;
        gen.resize((s + sample_every - 1) / sample_every);
        for (auto& g : gen) g.occ.assign(window, 0);
    }
    void access(uint64_t set, Line*, const AccessInfo& a) override {
        if (a.prefetch || set % sample_every) return;
        OptGen& g = gen[set / sample_every];
        uint64_t t = g.now++;
        g.occ[t % window] = 0;
        auto it = g.last.find(a.line);
        if (it != g.last.end() && t - it->second.first < window) {
            uint64_t start = it->second.first; bool fits = true;
            for (uint64_t k = start; k < t; ++k) if (g.occ[k % window] >= ways) { fits = false; break; }
            ++opt_access;
            if (fits) { for (uint64_t k = start; k < t; ++k) ++g.occ[k % window]; ++opt_hits; }
            uint8_t& c = pred[it->second.second];
            if (fits) { if (c < 7) ++c; } else if (c) --c;
        } else if (it != g.last.end()) { uint8_t& c = pred[it->second.second]; if (c) --c; }
        g.last[a.line] = {t, sig(a.pc)};
        if (g.last.size() > 4 * window) {  // drop entries older than the window
            for (auto i = g.last.begin(); i != g.last.end();) { if (t - i->second.first >= window) i = g.last.erase(i); else ++i; }
        }
    }
    bool friendly(uint64_t pc) const { return pred[sig(pc)] >= 4; }
    int victim(uint64_t, Line* l, const AccessInfo&) override {
        int v = invalid(l, ways); if (v >= 0) return v;
        for (unsigned w = 0; w < ways; ++w) if (l[w].rrpv == MAXR) return int(w);
        v = 0; for (unsigned w = 1; w < ways; ++w) if (l[w].rrpv > l[v].rrpv) v = int(w);
        uint8_t& c = pred[l[v].sig]; if (c) --c;  // evicting a friendly line: detrain
        return v;
    }
    void insert(int w, Line* l, const AccessInfo& a) {
        l[w].sig = sig(a.pc);
        if (friendly(a.pc)) {
            for (unsigned k = 0; k < ways; ++k) if (int(k) != w && l[k].valid && l[k].rrpv < MAXR - 1) ++l[k].rrpv;
            l[w].rrpv = 0;
        } else l[w].rrpv = MAXR;
    }
    void hit(uint64_t, int w, Line* l, const AccessInfo& a) override { insert(w, l, a); }
    void fill(uint64_t, int w, Line* l, const AccessInfo& a) override { insert(w, l, a); }
    uint64_t bits_per_line() const override { return 3 + sig_bits; }
    uint64_t extra_bits() const override { return pred.size() * 3 + gen.size() * window * (log2u(ways + 1) + 16 + sig_bits); }
    Json stats() const override { Json j = Json::object(); j["optgen_reuses"] = opt_access; j["optgen_hits"] = opt_hits; return j; }
};

// Belady OPT. Needs AccessInfo::next_use (position of the next access to the line in
// this cache's demand stream). Only the driver's first data level supplies it.
class Opt : public Replacement {
    std::vector<uint64_t> next;
public:
    std::string name() const override { return "opt"; }
    void init(uint64_t s, unsigned w) override { Replacement::init(s, w); next.assign(s * w, 0); }
    int victim(uint64_t set, Line* l, const AccessInfo&) override {
        int v = invalid(l, ways); if (v >= 0) return v;
        v = 0; for (unsigned w = 1; w < ways; ++w) if (next[set * ways + w] > next[set * ways + v]) v = int(w); return v;
    }
    void hit(uint64_t set, int w, Line*, const AccessInfo& a) override { next[set * ways + w] = a.next_use; }
    void fill(uint64_t set, int w, Line*, const AccessInfo& a) override { next[set * ways + w] = a.next_use; }
};

// Mockingjay (Shah, Jain & Lin, HPCA 2022): sampled sets learn a reuse distance per
// PC signature; each line holds an estimated time remaining (ETR) that ages with set
// accesses. The victim has the largest |ETR|; lines predicted to be scans go first.
class Mockingjay : public Replacement {
    unsigned sig_bits, sample_every, gran; int inf;
    std::vector<int> rdp;            // predicted reuse distance (set accesses / gran), -1 unknown
    std::vector<int16_t> etr;        // per line
    std::vector<uint64_t> clock;     // per set access counter
    struct S { uint64_t t; uint32_t sig; };
    std::vector<std::unordered_map<uint64_t, S>> sampler;
    size_t window = 0; uint64_t trained = 0, scans = 0;
    uint32_t sig(uint64_t pc, bool pf) const { return uint32_t(mix64(pc ^ (pf ? 0x9e3779b9 : 0)) & mask(sig_bits)); }
    void train(uint32_t s, int rd) {
        int& r = rdp[s];
        r = r < 0 ? rd : r + (rd > r ? std::min(1 + (rd - r) / 4, rd - r) : -std::min(1 + (r - rd) / 4, r - rd));
        ++trained;
    }
public:
    explicit Mockingjay(const Config& c) {
        sig_bits = unsigned(c.u("signature_bits", 11, 4, 20)); sample_every = unsigned(c.u("sample_every", 8, 1, 1024));
        gran = unsigned(c.u("granularity", 0, 0, 64));
        rdp.assign(size_t(1) << sig_bits, -1);
    }
    std::string name() const override { return "mockingjay"; }
    void init(uint64_t s, unsigned w) override {
        Replacement::init(s, w);
        if (!gran) gran = std::max(1u, w / 4);
        window = 8 * w; inf = int(window / gran) + 1;
        etr.assign(s * w, 0); clock.assign(s, 0); sampler.resize((s + sample_every - 1) / sample_every);
    }
    void access(uint64_t set, Line* l, const AccessInfo& a) override {
        uint64_t now = ++clock[set];
        if (now % gran == 0)
            for (unsigned w = 0; w < ways; ++w) if (l[w].valid && etr[set * ways + w] > -inf) --etr[set * ways + w];
        if (set % sample_every) return;
        auto& m = sampler[set / sample_every];
        auto it = m.find(a.line);
        if (it != m.end()) {
            uint64_t d = now - it->second.t;
            if (d <= window) train(it->second.sig, int(d / gran));
        }
        m[a.line] = {now, sig(a.pc, a.prefetch)};
        if (m.size() > window) {
            for (auto i = m.begin(); i != m.end();) {
                if (now - i->second.t > window) { train(i->second.sig, inf); ++scans; i = m.erase(i); }
                else ++i;
            }
        }
    }
    int predict(const AccessInfo& a) const { int r = rdp[sig(a.pc, a.prefetch)]; return r < 0 ? inf / 2 : r; }
    int victim(uint64_t set, Line* l, const AccessInfo&) override {
        int v = invalid(l, ways); if (v >= 0) return v;
        v = 0; int best = -1;
        for (unsigned w = 0; w < ways; ++w) { int e = std::abs(int(etr[set * ways + w])); if (e > best) { best = e; v = int(w); } }
        return v;
    }
    void hit(uint64_t set, int w, Line*, const AccessInfo& a) override { etr[set * ways + w] = int16_t(predict(a)); }
    void fill(uint64_t set, int w, Line*, const AccessInfo& a) override { etr[set * ways + w] = int16_t(predict(a)); }
    uint64_t bits_per_line() const override { return 6 + sig_bits; }
    uint64_t extra_bits() const override { return rdp.size() * 7 + sampler.size() * window * (sig_bits + 16 + 8); }
    Json stats() const override { Json j = Json::object(); j["rdp_updates"] = trained; j["scan_trainings"] = scans; return j; }
};

inline std::unique_ptr<Replacement> make_replacement(const Config& c) {
    std::string m = c.choice("replacement", "lru", {"lru", "random", "plru", "srrip", "brrip", "drrip", "ship", "hawkeye", "mockingjay", "opt"});
    if (m == "lru") return std::make_unique<Lru>();
    if (m == "random") return std::make_unique<RandomRepl>();
    if (m == "plru") return std::make_unique<Plru>();
    if (m == "srrip") return std::make_unique<Rrip>(0, c.at("rrip"));
    if (m == "brrip") return std::make_unique<Rrip>(1, c.at("rrip"));
    if (m == "drrip") return std::make_unique<Rrip>(2, c.at("rrip"));
    if (m == "ship") return std::make_unique<Rrip>(3, c.at("rrip"));
    if (m == "hawkeye") return std::make_unique<Hawkeye>(c.at("hawkeye"));
    if (m == "mockingjay") return std::make_unique<Mockingjay>(c.at("mockingjay"));
    return std::make_unique<Opt>();
}

// ------------------------------------------------------------------ prefetchers
struct PfAccess { uint64_t addr, line, pc, time; bool hit, first_use_of_prefetch, write; uint64_t latency; };
struct PfCand { uint64_t line; bool lower; };  // lower: fill the next level instead

class Prefetcher {
public:
    unsigned line_bits = 6, page_bits = 12;
    uint64_t issued = 0;
    virtual ~Prefetcher() = default;
    virtual std::string name() const = 0;
    virtual void train(const PfAccess& a, std::vector<PfCand>& out) = 0;
    virtual void filled(uint64_t, uint64_t, bool) {}  // line, ready cycle, was prefetch
    virtual void evicted(uint64_t) {}
    virtual uint64_t storage_bits() const = 0;
    virtual Json stats() const { return Json::object(); }
    bool same_page(uint64_t a, uint64_t b) const { return (a >> (page_bits - line_bits)) == (b >> (page_bits - line_bits)); }
};

class NextLine : public Prefetcher {
    unsigned degree; bool miss_only;
public:
    explicit NextLine(const Config& c) : degree(unsigned(c.u("degree", 1, 1, 64))), miss_only(c.choice("trigger", "miss", {"miss", "access"}) == "miss") {}
    std::string name() const override { return "next-line"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        if (miss_only && a.hit && !a.first_use_of_prefetch) return;
        for (unsigned k = 1; k <= degree; ++k) out.push_back({a.line + k, false});
    }
    uint64_t storage_bits() const override { return 0; }
};

class IpStride : public Prefetcher {
    struct E { uint64_t tag = 0; uint64_t last = 0; int64_t stride = 0; uint8_t conf = 0; bool valid = false; };
    std::vector<E> t; unsigned degree, distance;
public:
    explicit IpStride(const Config& c) : degree(unsigned(c.u("degree", 2, 1, 64))), distance(unsigned(c.u("distance", 1, 1, 64))) {
        uint64_t n = c.u("entries", 256, 1, 1u << 20); if (!pow2(n)) throw Error("ip-stride entries must be a power of two"); t.assign(n, E());
    }
    std::string name() const override { return "ip-stride"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        E& e = t[mix64(a.pc) & (t.size() - 1)];
        if (!e.valid || e.tag != a.pc) { e = E(); e.valid = true; e.tag = a.pc; e.last = a.addr; return; }
        int64_t s = int64_t(a.addr - e.last);
        if (s == 0) return;
        if (s == e.stride) { if (e.conf < 3) ++e.conf; } else { if (e.conf) --e.conf; if (e.conf == 0) e.stride = s; }
        e.last = a.addr;
        if (e.conf >= 2) {
            uint64_t prev = a.line;
            for (unsigned k = 0; k < degree; ++k) {
                uint64_t l = (a.addr + uint64_t(e.stride * int64_t(distance + k))) >> line_bits;
                if (l != prev) out.push_back({l, false});
                prev = l;
            }
        }
    }
    uint64_t storage_bits() const override { return t.size() * (16 + 48 + 20 + 2 + 1); }
};

class Stream : public Prefetcher {
    struct S { bool valid = false; uint64_t last = 0, head = 0; int dir = 0; unsigned conf = 0; uint64_t stamp = 0; };
    std::vector<S> s; unsigned degree, distance, window; uint64_t clock = 0;
public:
    explicit Stream(const Config& c) : degree(unsigned(c.u("degree", 4, 1, 64))), distance(unsigned(c.u("distance", 2, 1, 128))), window(unsigned(c.u("window", 16, 1, 1024))) {
        s.assign(c.u("streams", 16, 1, 1024), S());
    }
    std::string name() const override { return "stream"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        if (a.hit && !a.first_use_of_prefetch) return;
        ++clock;
        S* m = nullptr;
        for (auto& x : s) if (x.valid && same_page(x.last, a.line) && (a.line > x.last ? a.line - x.last : x.last - a.line) <= window) { m = &x; break; }
        if (!m) {
            S* v = &s[0]; for (auto& x : s) { if (!x.valid) { v = &x; break; } if (x.stamp < v->stamp) v = &x; }
            *v = S(); v->valid = true; v->last = v->head = a.line; v->stamp = clock; return;
        }
        m->stamp = clock;
        if (a.line == m->last) return;
        int d = a.line > m->last ? 1 : -1;
        if (d == m->dir) { if (m->conf < 3) ++m->conf; } else { m->dir = d; m->conf = 0; m->head = a.line; }
        m->last = a.line;
        if (m->conf < 1) return;
        int64_t start = int64_t(a.line) + d * int64_t(distance);
        if (d > 0 ? int64_t(m->head) >= start : int64_t(m->head) <= start) start = int64_t(m->head) + d;
        for (unsigned k = 0; k < degree; ++k) {
            uint64_t l = uint64_t(start + d * int64_t(k));
            if (!same_page(l, a.line)) break;
            out.push_back({l, false}); m->head = l;
        }
    }
    uint64_t storage_bits() const override { return s.size() * (1 + 2 * 52 + 2 + 2); }
};

class Bop : public Prefetcher {
    std::vector<int> offsets; std::vector<int> score; std::vector<uint64_t> rr; unsigned rr_bits;
    size_t test = 0; unsigned round = 0; int best = 1; bool on = true;
    unsigned round_max, score_max, bad_score; uint64_t phases = 0;
    struct P { uint64_t ready, line; int offset; bool operator>(const P& o) const { return ready > o.ready; } };
    std::priority_queue<P, std::vector<P>, std::greater<P>> pending;
    void rr_insert(uint64_t line) { rr[line & (rr.size() - 1)] = (line >> rr_bits) | (uint64_t(1) << 63); }
    bool rr_hit(uint64_t line) const { return rr[line & (rr.size() - 1)] == ((line >> rr_bits) | (uint64_t(1) << 63)); }
public:
    explicit Bop(const Config& c) {
        uint64_t n = c.u("rr_entries", 256, 2, 1u << 16); if (!pow2(n)) throw Error("bop rr_entries must be a power of two");
        rr.assign(n, 0); rr_bits = log2u(n);
        round_max = unsigned(c.u("round_max", 100, 1, 10000)); score_max = unsigned(c.u("score_max", 31, 1, 1000)); bad_score = unsigned(c.u("bad_score", 1, 0, 1000));
        int maxo = int(c.u("max_offset", 256, 1, 4096));
        for (int k = 1; k <= maxo; ++k) { int x = k; for (int p : {2, 3, 5}) while (x % p == 0) x /= p; if (x == 1) offsets.push_back(k); }
        score.assign(offsets.size(), 0);
    }
    std::string name() const override { return "bop"; }
    void filled(uint64_t line, uint64_t ready, bool pf) override { if (pf) pending.push({ready, line, best}); else pending.push({ready, line, 0}); }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        while (!pending.empty() && pending.top().ready <= a.time) {
            auto p = pending.top(); pending.pop();
            if (p.offset) rr_insert(p.line - uint64_t(p.offset)); else if (!on) rr_insert(p.line);
        }
        if (a.hit && !a.first_use_of_prefetch) return;  // trigger: miss or first use of a prefetched line
        uint64_t x = a.line;
        if (rr_hit(x - uint64_t(offsets[test]))) ++score[test];
        bool end = score[test] >= int(score_max);
        if (++test == offsets.size()) { test = 0; if (++round >= round_max) end = true; }
        if (end) {
            size_t b = 0; for (size_t k = 1; k < score.size(); ++k) if (score[k] > score[b]) b = k;
            on = score[b] > int(bad_score); best = offsets[b]; ++phases;
            std::fill(score.begin(), score.end(), 0); test = 0; round = 0;
        }
        if (on) { uint64_t l = x + uint64_t(best); if (same_page(l, x)) out.push_back({l, false}); }
    }
    uint64_t storage_bits() const override { return rr.size() * 12 + score.size() * 5 + 16; }
    Json stats() const override { Json j = Json::object(); j["offset"] = best; j["enabled"] = on; j["phases"] = phases; return j; }
};

class Spp : public Prefetcher {
    struct St { bool valid = false; uint64_t page = 0; unsigned last = 0; uint32_t sig = 0; uint64_t stamp = 0; };
    struct Pt { unsigned csig = 0; int delta[4] = {0, 0, 0, 0}; unsigned cd[4] = {0, 0, 0, 0}; };
    std::vector<St> st; std::vector<Pt> pt; double thr; unsigned depth; uint64_t clock = 0; unsigned sig_bits = 12;
    uint32_t next_sig(uint32_t s, int d) const { uint32_t enc = d < 0 ? uint32_t((-d) & 63) | 64 : uint32_t(d & 63); return ((s << 3) ^ enc) & uint32_t(mask(sig_bits)); }
public:
    explicit Spp(const Config& c) {
        st.assign(c.u("st_entries", 256, 1, 1u << 16), St()); uint64_t p = c.u("pt_entries", 512, 1, 1u << 16);
        if (!pow2(p)) throw Error("spp pt_entries must be a power of two");
        pt.assign(p, Pt()); thr = c.f("threshold", 0.25, 0.0, 1.0); depth = unsigned(c.u("max_depth", 8, 1, 64));
    }
    std::string name() const override { return "spp"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        unsigned lines_per_page = 1u << (page_bits - line_bits);
        uint64_t page = a.line / lines_per_page; unsigned off = unsigned(a.line % lines_per_page);
        ++clock;
        St* e = nullptr; for (auto& x : st) if (x.valid && x.page == page) { e = &x; break; }
        if (!e) {
            e = &st[0]; for (auto& x : st) { if (!x.valid) { e = &x; break; } if (x.stamp < e->stamp) e = &x; }
            *e = St(); e->valid = true; e->page = page; e->last = off; e->sig = 0; e->stamp = clock; return;
        }
        e->stamp = clock;
        int d = int(off) - int(e->last);
        if (d == 0) return;
        Pt& p = pt[e->sig & (pt.size() - 1)];
        int slot = -1; for (int k = 0; k < 4; ++k) if (p.cd[k] && p.delta[k] == d) slot = k;
        if (slot < 0) { slot = 0; for (int k = 1; k < 4; ++k) if (p.cd[k] < p.cd[slot]) slot = k; p.delta[slot] = d; p.cd[slot] = 0; }
        ++p.cd[slot]; ++p.csig;
        if (p.csig >= 15) { p.csig >>= 1; for (auto& x : p.cd) x >>= 1; }
        e->sig = next_sig(e->sig, d); e->last = off;
        // Lookahead along the most confident path.
        uint32_t sig = e->sig; double conf = 1.0; int base = int(off);
        for (unsigned level = 0; level < depth; ++level) {
            const Pt& q = pt[sig & (pt.size() - 1)];
            if (!q.csig) break;
            int bestk = -1; double bestc = 0;
            for (int k = 0; k < 4; ++k) {
                if (!q.cd[k]) continue;
                double c = conf * double(q.cd[k]) / double(q.csig);
                if (c >= thr) {
                    int t = base + q.delta[k];
                    if (t >= 0 && t < int(lines_per_page)) out.push_back({page * lines_per_page + unsigned(t), false});
                }
                if (c > bestc) { bestc = c; bestk = k; }
            }
            if (bestk < 0 || bestc < thr) break;
            conf = bestc; base += q.delta[bestk]; sig = next_sig(sig, q.delta[bestk]);
            if (base < 0 || base >= int(lines_per_page)) break;
        }
    }
    uint64_t storage_bits() const override { return st.size() * (1 + 16 + 6 + sig_bits + 8) + pt.size() * (4 + 4 * (7 + 4)); }
};

class Sms : public Prefetcher {
    unsigned region_lines;
    struct F { bool valid = false; uint64_t region = 0, pc = 0; unsigned trig = 0; uint64_t stamp = 0; };
    struct A { bool valid = false; uint64_t region = 0, pc = 0; unsigned trig = 0; uint64_t pattern = 0, stamp = 0; };
    bool bingo = false; uint64_t long_hits = 0, short_hits = 0;
    uint64_t long_key(uint64_t pc, uint64_t line) const { return mix64(pc * 31 + line + 0x7777); }
    struct H { bool valid = false; uint64_t tag = 0, pattern = 0; };
    std::vector<F> ft; std::vector<A> at; std::vector<H> pht; uint64_t clock = 0; uint64_t generations = 0;
    uint64_t key(uint64_t pc, unsigned trig) const { return mix64(pc ^ (uint64_t(trig) << 48)); }
    void finish(A& a) {
        if (!a.valid) return;
        uint64_t k = key(a.pc, a.trig); H& h = pht[k & (pht.size() - 1)];
        h.valid = true; h.tag = k >> 20; h.pattern = a.pattern; a.valid = false; ++generations;
        if (bingo) {  // Bingo: also keep the pattern under the long event (PC + trigger address)
            uint64_t lk = long_key(a.pc, a.region * region_lines + a.trig); H& g = pht[lk & (pht.size() - 1)];
            g.valid = true; g.tag = lk >> 20; g.pattern = a.pattern;
        }
    }
public:
    explicit Sms(const Config& c, bool b = false) : bingo(b) {
        uint64_t rb = c.u("region_bytes", 2048, 128, 1u << 16); if (!pow2(rb)) throw Error("sms region_bytes must be a power of two");
        region_lines = unsigned(rb / 64);
        if (region_lines > 64) throw Error("sms region must hold at most 64 lines");
        ft.assign(c.u("filter_entries", 32, 1, 4096), F()); at.assign(c.u("accumulation_entries", 64, 1, 4096), A());
        uint64_t p = c.u("pht_entries", 2048, 1, 1u << 20); if (!pow2(p)) throw Error("sms pht_entries must be a power of two");
        pht.assign(p, H());
    }
    std::string name() const override { return bingo ? "bingo" : "sms"; }
    void evicted(uint64_t line) override {
        uint64_t r = line / region_lines;
        for (auto& a : at) if (a.valid && a.region == r) finish(a);
        for (auto& f : ft) if (f.valid && f.region == r) f.valid = false;
    }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        ++clock;
        uint64_t r = a.line / region_lines; unsigned off = unsigned(a.line % region_lines);
        for (auto& x : at) if (x.valid && x.region == r) { x.pattern |= uint64_t(1) << off; x.stamp = clock; return; }
        for (auto& f : ft) if (f.valid && f.region == r) {
            if (off == f.trig) return;
            A* v = &at[0]; for (auto& x : at) { if (!x.valid) { v = &x; break; } if (x.stamp < v->stamp) v = &x; }
            finish(*v);
            v->valid = true; v->region = r; v->pc = f.pc; v->trig = f.trig; v->pattern = (uint64_t(1) << f.trig) | (uint64_t(1) << off); v->stamp = clock;
            f.valid = false; return;
        }
        // Trigger access of a new generation.
        uint64_t k = key(a.pc, off); const H* h = &pht[k & (pht.size() - 1)];
        bool found = h->valid && h->tag == (k >> 20);
        if (bingo) {
            uint64_t lk = long_key(a.pc, a.line); const H* g = &pht[lk & (pht.size() - 1)];
            if (g->valid && g->tag == (lk >> 20)) { h = g; found = true; ++long_hits; }
            else if (found) ++short_hits;
        }
        if (found)
            for (unsigned b = 0; b < region_lines; ++b) if (b != off && (h->pattern >> b) & 1) out.push_back({r * region_lines + b, false});
        F* v = &ft[0]; for (auto& x : ft) { if (!x.valid) { v = &x; break; } if (x.stamp < v->stamp) v = &x; }
        v->valid = true; v->region = r; v->pc = a.pc; v->trig = off; v->stamp = clock;
    }
    uint64_t storage_bits() const override { return ft.size() * (36 + 16 + 5) + at.size() * (36 + 16 + 5 + region_lines) + pht.size() * (24 + region_lines); }
    Json stats() const override {
        Json j = Json::object(); j["generations"] = generations;
        if (bingo) { j["long_event_hits"] = long_hits; j["short_event_hits"] = short_hits; }
        return j;
    }
};

class Berti : public Prefetcher {
    struct Hist { uint64_t line = 0, time = 0; };
    struct D { int64_t delta = 0; unsigned count = 0; uint8_t status = 0; };  // status 0 none, 1 L1, 2 L2
    struct E { bool valid = false; uint64_t tag = 0; std::vector<Hist> h; size_t pos = 0; std::vector<D> d; unsigned searches = 0; uint64_t stamp = 0; };
    std::vector<E> t; unsigned hist_n, delta_n, round; double hi, mid; uint64_t clock = 0;
    E& entry(uint64_t pc) {
        ++clock;
        for (auto& e : t) if (e.valid && e.tag == pc) { e.stamp = clock; return e; }
        E* v = &t[0]; for (auto& e : t) { if (!e.valid) { v = &e; break; } if (e.stamp < v->stamp) v = &e; }
        *v = E(); v->valid = true; v->tag = pc; v->h.assign(hist_n, Hist()); v->d.assign(delta_n, D()); v->stamp = clock;
        return *v;
    }
public:
    explicit Berti(const Config& c) {
        t.assign(c.u("ip_entries", 64, 1, 4096), E()); hist_n = unsigned(c.u("history", 16, 1, 256)); delta_n = unsigned(c.u("deltas", 16, 1, 256));
        round = unsigned(c.u("round", 16, 1, 1024)); hi = c.f("l1_coverage", 0.65, 0, 1); mid = c.f("l2_coverage", 0.35, 0, 1);
    }
    std::string name() const override { return "berti"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        E& e = entry(a.pc);
        bool learn = !a.hit || a.first_use_of_prefetch;
        if (learn) {
            uint64_t lat = std::max<uint64_t>(a.latency, 1);
            bool counted = false;
            for (auto& x : e.h) {
                if (!x.time || x.time + lat > a.time) continue;  // would not have been timely
                int64_t delta = int64_t(a.line - x.line);
                if (!delta || delta > 1024 || delta < -1024) continue;
                D* slot = nullptr; for (auto& y : e.d) if (y.count && y.delta == delta) slot = &y;
                if (!slot) { slot = &e.d[0]; for (auto& y : e.d) if (y.count < slot->count) slot = &y; if (slot->count) continue; slot->delta = delta; slot->count = 0; slot->status = 0; }
                ++slot->count; counted = true;
            }
            (void)counted;
            if (++e.searches >= round) {
                for (auto& y : e.d) { double cov = double(y.count) / e.searches; y.status = cov >= hi ? 1 : cov >= mid ? 2 : 0; y.count = y.status ? 1 : 0; }
                e.searches = 0;
            }
            e.h[e.pos] = {a.line, a.time ? a.time : 1}; e.pos = (e.pos + 1) % e.h.size();
        }
        for (auto& y : e.d) if (y.status) {
            uint64_t l = a.line + uint64_t(y.delta);
            out.push_back({l, y.status == 2});
        }
    }
    uint64_t storage_bits() const override { return t.size() * (16 + hist_n * (24 + 16) + delta_n * (13 + 4 + 2)); }
};

// IPCP (Pakalapati & Panda, ISCA 2020): classify each load IP as global stream,
// constant stride or complex stride, and prefetch by class (next line otherwise).
class Ipcp : public Prefetcher {
    struct Ip { bool valid = false; uint64_t tag = 0, last = 0; int64_t stride = 0; uint8_t conf = 0; uint32_t sig = 0; };
    struct Cs { int64_t stride = 0; uint8_t conf = 0; };
    struct Rs { bool valid = false; uint64_t region = 0, bits = 0, last = 0, stamp = 0; int dir = 0; };
    std::vector<Ip> ip; std::vector<Cs> cspt; std::vector<Rs> rst;
    unsigned cs_degree, cplx_degree, gs_degree, region_lines = 32; uint64_t clock = 0;
    uint64_t by_class[4] = {0, 0, 0, 0};
public:
    explicit Ipcp(const Config& c) {
        uint64_t n = c.u("ip_entries", 64, 1, 1u << 16); if (!pow2(n)) throw Error("ipcp ip_entries must be a power of two");
        ip.assign(n, Ip()); cspt.assign(c.u("cspt_entries", 128, 2, 1u << 16), Cs()); rst.assign(c.u("regions", 8, 1, 1024), Rs());
        cs_degree = unsigned(c.u("cs_degree", 3, 1, 32)); cplx_degree = unsigned(c.u("cplx_degree", 3, 1, 32)); gs_degree = unsigned(c.u("gs_degree", 6, 1, 64));
    }
    std::string name() const override { return "ipcp"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        ++clock;
        uint64_t r = a.line / region_lines;
        Rs* g = nullptr; for (auto& x : rst) if (x.valid && x.region == r) { g = &x; break; }
        if (!g) { g = &rst[0]; for (auto& x : rst) { if (!x.valid) { g = &x; break; } if (x.stamp < g->stamp) g = &x; } *g = Rs(); g->valid = true; g->region = r; g->last = a.line; }
        g->stamp = clock; g->bits |= uint64_t(1) << (a.line % region_lines);
        if (a.line != g->last) { g->dir += a.line > g->last ? 1 : -1; g->dir = std::max(-8, std::min(8, g->dir)); }
        g->last = a.line;
        bool dense = __builtin_popcountll(g->bits) * 4 >= int(region_lines) * 3;
        Ip& e = ip[mix64(a.pc) & (ip.size() - 1)];
        if (!e.valid || e.tag != a.pc) { e = Ip(); e.valid = true; e.tag = a.pc; e.last = a.line; return; }
        int64_t st = int64_t(a.line) - int64_t(e.last);
        if (st == 0) return;
        if (st == e.stride) { if (e.conf < 3) ++e.conf; } else { if (e.conf) --e.conf; if (!e.conf) e.stride = st; }
        Cs& cs = cspt[e.sig % cspt.size()];
        if (cs.stride == st) { if (cs.conf < 3) ++cs.conf; } else { if (cs.conf) --cs.conf; if (!cs.conf) cs.stride = st; }
        e.sig = uint32_t(((e.sig << 1) ^ uint32_t(st & 63)) & 127);
        e.last = a.line;
        if (dense && std::abs(g->dir) >= 6) {
            ++by_class[0]; int d = g->dir > 0 ? 1 : -1;
            for (unsigned k = 1; k <= gs_degree; ++k) out.push_back({uint64_t(int64_t(a.line) + d * int64_t(k)), false});
        } else if (e.conf >= 2) {
            ++by_class[1];
            for (unsigned k = 1; k <= cs_degree; ++k) out.push_back({uint64_t(int64_t(a.line) + e.stride * int64_t(k)), false});
        } else if (cspt[e.sig % cspt.size()].conf >= 1) {
            ++by_class[2]; uint32_t sig = e.sig; int64_t l = int64_t(a.line);
            for (unsigned k = 0; k < cplx_degree; ++k) {
                const Cs& q = cspt[sig % cspt.size()]; if (!q.conf || !q.stride) break;
                l += q.stride; out.push_back({uint64_t(l), false}); sig = uint32_t(((sig << 1) ^ uint32_t(q.stride & 63)) & 127);
            }
        } else if (!a.hit) { ++by_class[3]; out.push_back({a.line + 1, false}); }
    }
    uint64_t storage_bits() const override { return ip.size() * (9 + 6 + 7 + 2 + 7 + 1) + cspt.size() * 9 + rst.size() * (36 + 32 + 4 + 1); }
    Json stats() const override {
        Json j = Json::object(); j["global_stream"] = by_class[0]; j["constant_stride"] = by_class[1]; j["complex_stride"] = by_class[2]; j["next_line"] = by_class[3];
        return j;
    }
};

// Entangling instruction prefetcher: pairs a source line with a missed destination
// line whose fetch latency the source access would have covered.
class Eip : public Prefetcher {
    struct Hist { uint64_t line = 0, time = 0; };
    struct E { bool valid = false; uint64_t src = 0; uint64_t dst[4] = {0, 0, 0, 0}; uint8_t n = 0; };
    std::deque<Hist> h; size_t hist_n; std::vector<E> t; unsigned dests; uint64_t pairs = 0; uint64_t last_line = UINT64_MAX;
public:
    explicit Eip(const Config& c) {
        hist_n = c.u("history", 32, 1, 4096); dests = unsigned(c.u("destinations", 2, 1, 4));
        uint64_t n = c.u("entries", 4096, 1, 1u << 20); if (!pow2(n)) throw Error("eip entries must be a power of two");
        t.assign(n, E());
    }
    std::string name() const override { return "eip"; }
    void train(const PfAccess& a, std::vector<PfCand>& out) override {
        if (a.line == last_line) return;
        last_line = a.line;
        if (!a.hit || a.first_use_of_prefetch) {
            uint64_t lat = std::max<uint64_t>(a.latency, 1);
            for (auto it = h.rbegin(); it != h.rend(); ++it) if (it->time + lat <= a.time) {
                E& e = t[mix64(it->line) & (t.size() - 1)];
                if (!e.valid || e.src != it->line) { e = E(); e.valid = true; e.src = it->line; }
                bool have = false; for (unsigned k = 0; k < e.n; ++k) if (e.dst[k] == a.line) have = true;
                if (!have) { if (e.n < dests) e.dst[e.n++] = a.line; else { for (unsigned k = 1; k < dests; ++k) e.dst[k - 1] = e.dst[k]; e.dst[dests - 1] = a.line; } ++pairs; }
                break;
            }
        }
        const E& e = t[mix64(a.line) & (t.size() - 1)];
        if (e.valid && e.src == a.line) for (unsigned k = 0; k < e.n; ++k) out.push_back({e.dst[k], false});
        h.push_back({a.line, a.time}); if (h.size() > hist_n) h.pop_front();
    }
    uint64_t storage_bits() const override { return t.size() * (1 + 20 + dests * 20) + hist_n * (58 + 20); }
    Json stats() const override { Json j = Json::object(); j["entangled_pairs"] = pairs; return j; }
};

inline std::unique_ptr<Prefetcher> make_prefetcher(const Config& c) {
    std::string k = c.choice("kind", "next-line", {"next-line", "ip-stride", "stream", "bop", "spp", "sms", "bingo", "ipcp", "berti", "eip"});
    if (k == "next-line") return std::make_unique<NextLine>(c);
    if (k == "ip-stride") return std::make_unique<IpStride>(c);
    if (k == "stream") return std::make_unique<Stream>(c);
    if (k == "bop") return std::make_unique<Bop>(c);
    if (k == "spp") return std::make_unique<Spp>(c);
    if (k == "sms") return std::make_unique<Sms>(c);
    if (k == "bingo") return std::make_unique<Sms>(c, true);
    if (k == "ipcp") return std::make_unique<Ipcp>(c);
    if (k == "berti") return std::make_unique<Berti>(c);
    return std::make_unique<Eip>(c);
}

// ------------------------------------------------------------------ cache
class Cache {
public:
    std::string name; uint64_t sets; unsigned ways, line_bits, latency, mshr; bool perfect;
    std::vector<Line> lines; std::unique_ptr<Replacement> repl; std::vector<std::unique_ptr<Prefetcher>> pfs;
    Cache* next = nullptr; uint64_t memory_latency = 200;
    std::priority_queue<uint64_t, std::vector<uint64_t>, std::greater<uint64_t>> outstanding;
    std::unordered_map<uint64_t, uint64_t> pollution; uint64_t pollution_cap;
    // stats
    uint64_t d_access = 0, d_hit = 0, d_miss = 0, d_late = 0, d_pollution = 0, writebacks = 0;
    uint64_t pf_req = 0, pf_present = 0, pf_full = 0, pf_issued = 0, pf_useful = 0, pf_useless = 0, pf_lower = 0;
    uint64_t lower_access = 0, lower_miss = 0, total_latency = 0;
    std::vector<PfCand> cand;

    Cache(const std::string& n, const Config& c, unsigned def_lat, uint64_t def_kib, unsigned def_ways) : name(n) {
        line_bits = unsigned(log2u(c.u("line_bytes", 64, 4, 4096)));
        if (!pow2(uint64_t(1) << line_bits)) throw Error("line_bytes must be a power of two");
        ways = unsigned(c.u("ways", def_ways, 1, 128));
        uint64_t bytes = c.u("size_kib", def_kib, 1, 1u << 22) * 1024;
        uint64_t nlines = bytes >> line_bits;
        if (nlines % ways || !pow2(nlines / ways)) throw Error(n + ": size/line/ways must give a power-of-two set count");
        sets = nlines / ways; latency = unsigned(c.u("latency", def_lat, 0, 1000)); mshr = unsigned(c.u("prefetch_queue", 16, 1, 4096));
        perfect = c.flag("perfect", false);
        pollution_cap = c.u("pollution_filter", 1024, 0, 1u << 20);
        lines.assign(nlines, Line());
        repl = make_replacement(c); repl->init(sets, ways);
        size_t np = c.list("prefetchers");
        for (size_t i = 0; i < np; ++i) { auto p = make_prefetcher(c.at("prefetchers", i)); p->line_bits = line_bits; pfs.push_back(std::move(p)); }
    }
    Line* find(uint64_t line, uint64_t& set, int& way) {
        set = line & (sets - 1); Line* l = &lines[set * ways];
        for (unsigned w = 0; w < ways; ++w) if (l[w].valid && l[w].tag == line) { way = int(w); return &l[w]; }
        way = -1; return nullptr;
    }
    bool contains(uint64_t line) { uint64_t s; int w; return find(line, s, w) != nullptr; }
    uint64_t lower(uint64_t line, uint64_t pc, uint64_t t, bool pf) {
        if (next) return next->access(line << line_bits, pc, t, false, pf, UINT64_MAX, nullptr);
        return t + memory_latency;
    }
    void install(uint64_t line, uint64_t set, uint64_t ready, bool pf, const AccessInfo& ai, uint64_t t) {
        Line* l = &lines[set * ways];
        int v = repl->victim(set, l, ai);
        Line& old = l[v];
        if (old.valid) {
            repl->evict(set, v, old);
            if (old.prefetched) ++pf_useless;
            if (old.dirty) ++writebacks;
            for (auto& p : pfs) p->evicted(old.tag);
            if (pf && pollution_cap) { if (pollution.size() >= pollution_cap) pollution.erase(pollution.begin()); pollution[old.tag] = t; }
        }
        old = Line(); old.valid = true; old.tag = line; old.ready = ready; old.prefetched = pf; old.by_prefetch = pf;
        old.fill_latency = uint32_t(ready > t ? ready - t : 0); old.dirty = ai.write;
        repl->fill(set, v, l, ai);
        for (auto& p : pfs) p->filled(line, ready, pf);
    }
    // Demand (or upper-level) access. Returns the completion cycle.
    uint64_t access(uint64_t addr, uint64_t pc, uint64_t t, bool write, bool from_upper_pf, uint64_t next_use, bool* hit_out) {
        uint64_t line = addr >> line_bits, set; int way;
        AccessInfo ai; ai.line = line; ai.pc = pc; ai.time = t; ai.write = write; ai.prefetch = from_upper_pf; ai.next_use = next_use;
        if (perfect) { if (!from_upper_pf) { ++d_access; ++d_hit; total_latency += latency; } if (hit_out) *hit_out = true; return t + latency; }
        repl->access(line & (sets - 1), &lines[(line & (sets - 1)) * ways], ai);
        Line* l = find(line, set, way);
        uint64_t done; bool first_use = false;
        if (from_upper_pf) ++lower_access; else ++d_access;
        if (l) {
            done = std::max<uint64_t>(t + latency, l->ready);
            if (!from_upper_pf) {
                ++d_hit;
                if (l->prefetched) { ++pf_useful; first_use = true; l->prefetched = false; if (l->ready > t + latency) ++d_late; }
                if (write) l->dirty = true;
            }
            repl->hit(set, way, &lines[set * ways], ai);
        } else {
            if (from_upper_pf) ++lower_miss;
            else {
                ++d_miss;
                auto it = pollution.find(line);
                if (it != pollution.end()) { ++d_pollution; pollution.erase(it); }
            }
            done = lower(line, pc, t + latency, from_upper_pf);
            install(line, set, done, from_upper_pf, ai, t);
        }
        if (hit_out) *hit_out = l != nullptr;
        if (!from_upper_pf) {
            total_latency += done - t;
            if (!pfs.empty()) {
                PfAccess pa{addr, line, pc, t, l != nullptr, first_use, write, done - t};
                for (auto& p : pfs) {
                    cand.clear(); p->train(pa, cand);
                    for (auto& c : cand) issue(c, pc, t, *p);
                }
            }
        }
        return done;
    }
    void issue(const PfCand& c, uint64_t pc, uint64_t t, Prefetcher& p) {
        ++pf_req;
        if (c.lower) {
            if (next && !contains(c.line)) { ++pf_lower; next->prefetch_into(c.line << line_bits >> next->line_bits, pc, t); }
            return;
        }
        prefetch_into(c.line, pc, t, &p);
    }
    // Prefetch one line into this level.
    void prefetch_into(uint64_t line, uint64_t pc, uint64_t t, Prefetcher* p = nullptr) {
        if (perfect) return;
        uint64_t set; int way;
        if (find(line, set, way)) { ++pf_present; return; }
        while (!outstanding.empty() && outstanding.top() <= t) outstanding.pop();
        if (outstanding.size() >= mshr) { ++pf_full; return; }
        uint64_t done = lower(line, pc, t + latency, true);
        AccessInfo ai; ai.line = line; ai.pc = pc; ai.time = t; ai.prefetch = true;
        install(line, set, done, true, ai, t);
        outstanding.push(done); ++pf_issued; if (p) ++p->issued;
    }
    Storage storage() const {
        Storage s; uint64_t tag_bits = 48 - line_bits - log2u(sets);
        s.add("data", lines.size() << (line_bits + 3));
        s.add("tags", lines.size() * (tag_bits + 1 + 1 + 1 + repl->bits_per_line()));
        s.add("replacement_extra", repl->extra_bits());
        uint64_t pb = 0; for (auto& p : pfs) pb += p->storage_bits();
        s.add("prefetchers", pb);
        return s;
    }
    Json stats(uint64_t instructions) const {
        Json j = Json::object();
        j["size_kib"] = double(lines.size() << line_bits) / 1024.0; j["ways"] = ways; j["sets"] = sets; j["latency"] = latency;
        j["replacement"] = repl->name(); j["perfect"] = perfect;
        j["demand_accesses"] = d_access; j["demand_hits"] = d_hit; j["demand_misses"] = d_miss;
        j["demand_mpki"] = per_kilo(d_miss, instructions); j["miss_rate"] = ratio(double(d_miss), double(d_access));
        j["average_latency"] = ratio(double(total_latency), double(d_access));
        j["prefetch_requests_from_upper"] = lower_access; j["prefetch_misses_from_upper"] = lower_miss; j["writebacks"] = writebacks;
        Json p = Json::object();
        p["requested"] = pf_req; p["dropped_present"] = pf_present; p["dropped_queue_full"] = pf_full; p["issued"] = pf_issued; p["sent_to_lower"] = pf_lower;
        p["useful"] = pf_useful; p["late"] = d_late; p["useless_evicted"] = pf_useless; p["pollution_misses"] = d_pollution;
        p["accuracy"] = ratio(double(pf_useful), double(pf_issued));
        p["coverage"] = ratio(double(pf_useful), double(pf_useful + d_miss));
        Json names = Json::array();
        for (auto& x : pfs) { Json q = x->stats(); q["kind"] = x->name(); q["issued"] = x->issued; names.push(q); }
        p["prefetchers"] = names;
        j["prefetch"] = p;
        j["replacement_stats"] = repl->stats();
        return j;
    }
};

// ------------------------------------------------------------------ TLB and page walks
class Tlb {
public:
    struct E { bool valid = false; uint64_t vpn = 0, stamp = 0; };
    std::vector<E> e; uint64_t sets; unsigned ways, latency; uint64_t clock = 0, access = 0, miss = 0;
    Tlb(const Config& c, uint64_t def_entries, unsigned def_ways, unsigned def_lat) {
        uint64_t n = c.u("entries", def_entries, 1, 1u << 20); ways = unsigned(c.u("ways", def_ways, 1, 1024));
        if (n % ways || !pow2(n / ways)) throw Error("TLB entries/ways must give a power-of-two set count");
        sets = n / ways; latency = unsigned(c.u("latency", def_lat, 0, 1000)); e.assign(n, E());
    }
    bool lookup(uint64_t vpn) {
        ++access; E* s = &e[(vpn & (sets - 1)) * ways];
        for (unsigned w = 0; w < ways; ++w) if (s[w].valid && s[w].vpn == vpn) { s[w].stamp = ++clock; return true; }
        ++miss; return false;
    }
    void fill(uint64_t vpn) {
        E* s = &e[(vpn & (sets - 1)) * ways]; E* v = &s[0];
        for (unsigned w = 0; w < ways; ++w) { if (!s[w].valid) { v = &s[w]; break; } if (s[w].stamp < v->stamp) v = &s[w]; }
        v->valid = true; v->vpn = vpn; v->stamp = ++clock;
    }
    Json stats(uint64_t instructions) const {
        Json j = Json::object(); j["entries"] = uint64_t(e.size()); j["ways"] = ways; j["accesses"] = access; j["misses"] = miss; j["mpki"] = per_kilo(miss, instructions); return j;
    }
};

// Radix page-table walker with per-level page walk caches. Page-table entry addresses
// are synthesized from the VPN so walks can share cache lines (8-byte entries).
class Mmu {
public:
    unsigned page_bits, levels, level_bits; std::unique_ptr<Tlb> l1, l2; std::vector<std::unique_ptr<Tlb>> pwc;
    bool through_cache; unsigned walk_ref_latency; Cache* cache = nullptr;
    std::string context_policy; uint64_t ctx_tag = 0, context_flushes = 0;
    uint64_t walks = 0, walk_refs = 0, walk_cycles = 0;
    explicit Mmu(const Config& c) {
        page_bits = unsigned(c.u("page_bits", 12, 10, 30)); levels = unsigned(c.u("levels", 3, 1, 5)); level_bits = unsigned(c.u("level_bits", 9, 1, 16));
        l1 = std::make_unique<Tlb>(c.at("l1"), 64, 4, 0);
        if (c.at("l2").any() || c.flag("l2_enabled", true)) l2 = std::make_unique<Tlb>(c.at("l2"), 1024, 8, 8);
        for (unsigned k = 0; k + 1 < levels; ++k) pwc.push_back(std::make_unique<Tlb>(c.at("pwc", k), 16, 16, 0));
        context_policy = c.choice("context", "shared", {"shared", "flush", "tagged"});
        through_cache = c.flag("walk_through_cache", true); walk_ref_latency = unsigned(c.u("walk_ref_latency", 30, 0, 10000));
    }
    // Returns the cycle at which the translation is available.
    void context(uint64_t ctx) {
        if (context_policy == "flush") {
            for (Tlb* x : {l1.get(), l2.get()}) if (x) for (auto& e : x->e) e.valid = false;
            for (auto& p : pwc) for (auto& e : p->e) e.valid = false;
            ++context_flushes;
        } else if (context_policy == "tagged") ctx_tag = (ctx & 0xffff) << 48;
    }
    uint64_t translate(uint64_t vaddr, uint64_t pc, uint64_t t) {
        uint64_t vpn = (vaddr >> page_bits) ^ ctx_tag;
        if (l1->lookup(vpn)) return t + l1->latency;
        t += l1->latency;
        if (l2) { if (l2->lookup(vpn)) { l1->fill(vpn); return t + l2->latency; } t += l2->latency; }
        ++walks; uint64_t start = t;
        // Highest cached upper level: skip the references it covers.
        unsigned first = 0;
        for (int k = int(levels) - 2; k >= 0; --k) {
            uint64_t prefix = vpn >> (level_bits * (levels - 1 - unsigned(k)));
            if (pwc[k]->lookup(prefix + (uint64_t(k) << 56))) { first = unsigned(k) + 1; break; }
        }
        for (unsigned k = first; k < levels; ++k) {
            uint64_t prefix = vpn >> (level_bits * (levels - 1 - k));
            uint64_t pte = (uint64_t(0x7f) << 40) + (uint64_t(k) << 36) + prefix * 8;
            ++walk_refs;
            if (through_cache && cache) t = cache->access(pte, pc, t, false, false, UINT64_MAX, nullptr);
            else t += walk_ref_latency;
            if (k + 1 < levels) pwc[k]->fill(prefix + (uint64_t(k) << 56));
        }
        walk_cycles += t - start;
        if (l2) l2->fill(vpn);
        l1->fill(vpn);
        return t;
    }
    Storage storage() const {
        Storage s; s.add("l1", l1->e.size() * (64 - page_bits + 44)); if (l2) s.add("l2", l2->e.size() * (64 - page_bits + 44));
        uint64_t p = 0; for (auto& x : pwc) p += x->e.size() * (64 + 44); s.add("pwc", p); return s;
    }
    Json stats(uint64_t instructions) const {
        Json j = Json::object(); j["l1"] = l1->stats(instructions); if (l2) j["l2"] = l2->stats(instructions);
        Json p = Json::array(); for (auto& x : pwc) p.push(x->stats(instructions)); j["pwc"] = p;
        j["walks"] = walks; j["walk_mpki"] = per_kilo(walks, instructions); j["walk_memory_references"] = walk_refs;
        j["average_walk_cycles"] = ratio(double(walk_cycles), double(walks)); j["walks_through_cache"] = through_cache;
        j["context"] = context_policy; j["context_flushes"] = context_flushes;
        return j;
    }
};

}  // namespace csim
