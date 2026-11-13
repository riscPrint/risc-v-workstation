// Trace-driven studies that combine the component models. A study reads one trace
// and reports each configured component. See ComponentSims/README.md for the policy.
#pragma once
#include <fstream>
#include <unordered_map>
#include "direction.h"
#include "memory.h"
#include "misc.h"
#include "target.h"
#include "trace.h"

namespace csim {

inline void reset(Cache& c) {
    c.d_access = c.d_hit = c.d_miss = c.d_late = c.d_pollution = c.writebacks = 0;
    c.pf_req = c.pf_present = c.pf_full = c.pf_issued = c.pf_useful = c.pf_useless = c.pf_lower = 0;
    c.lower_access = c.lower_miss = c.total_latency = 0;
    for (auto& p : c.pfs) p->issued = 0;
}
inline void reset(Tlb& t) { t.access = t.miss = 0; }
inline void reset(Mmu& m) { reset(*m.l1); if (m.l2) reset(*m.l2); for (auto& p : m.pwc) reset(*p); m.walks = m.walk_refs = m.walk_cycles = 0; }
inline void reset(Btb& b) { for (auto& l : b.levels) l.lookups = l.hits = l.fills = l.evictions = 0; }
inline void reset(Ras& r) { r.pushes = r.pops = r.overflows = r.underflows = r.repairs = 0; }

// Per-branch outcome handed to the front-end timing model.
struct BranchOutcome {
    uint64_t ord, pc, target, block_start; uint8_t kind, len; bool taken, pred_taken, dir_miss, decode_redirect, exec_redirect;
    int btb_level; uint64_t wrong_target;  // first wrong-path fetch address (0 = unknown)
};

struct StaticBranch { uint64_t pc = 0; uint8_t kind = 0, len = 4; bool last_taken = false; uint64_t last_target = 0; };

class Frontend;

class BranchStudy {
public:
    std::unique_ptr<Direction> dir; std::unique_ptr<Btb> btb; std::unique_ptr<Ras> ras; std::unique_ptr<Indirect> ind;
    unsigned delay = 0; unsigned wrong_path = 0; bool learn_cfg = false;
    struct Pending { uint64_t pc; bool taken; DirMeta m; };
    std::deque<Pending> queue;
    std::unordered_map<uint64_t, StaticBranch> cfg;  // fetch-block start -> ending branch
    std::unordered_map<uint64_t, uint8_t> call_size; std::vector<uint64_t> shadow;
    uint64_t block_start = 0;
    uint64_t counts[7] = {0}, taken_counts[7] = {0};
    uint64_t dir_miss = 0, btb_miss = 0, btb_wrong = 0, ind_miss = 0, ret_miss = 0, wp_branches = 0, wp_stops = 0;
    struct PcStat { uint64_t execs = 0, taken = 0, dir_miss = 0, target_miss = 0; uint8_t kind = 0; };
    std::unordered_map<uint64_t, PcStat> per_pc;
    unsigned top_n = 20;
    std::ofstream predictions;
    Frontend* fe = nullptr;
    bool targets_available = true;

    explicit BranchStudy(const Config& c) {
        auto b = c.at("branch");
        if (b.any()) {
            dir = make_direction(b);
            delay = unsigned(b.u("update_delay", 0, 0, 4096));
        }
        if (c.at("btb").any()) btb = std::make_unique<Btb>(c.at("btb"));
        if (c.at("ras").any()) ras = std::make_unique<Ras>(c.at("ras"));
        if (c.at("indirect").any()) ind = make_indirect(c.at("indirect"));
        wrong_path = unsigned(c.u("wrong_path.branches", 0, 0, 1024));
        learn_cfg = wrong_path > 0 || c.at("frontend").any();
        top_n = unsigned(c.u("report.top_branches", 20, 0, 100000));
        std::string pf = c.str("report.predictions_file", "");
        if (!pf.empty()) { predictions.open(pf); if (!predictions) throw Error("cannot write predictions_file"); predictions << "rvw.csim-predictions/1\n"; }
    }
    bool active() const { return dir || btb || ras || ind; }

    void drain(size_t keep) {
        while (queue.size() > keep) { auto& p = queue.front(); dir->update(p.pc, p.taken, p.m); queue.pop_front(); }
    }

    uint64_t fallthrough(const Rec& r) {
        if (r.len) return r.pc + r.len;
        auto it = call_size.find(r.pc); return it == call_size.end() ? 0 : r.pc + it->second;
    }

    // Walk the learned static control flow for wrong-path RAS effects, then repair.
    void wrong_path_walk(uint64_t start) {
        if (!ras || !wrong_path || !start) return;
        auto cp = ras->save();
        uint64_t a = start;
        for (unsigned k = 0; k < wrong_path; ++k) {
            auto it = cfg.find(a);
            if (it == cfg.end()) { ++wp_stops; break; }
            const StaticBranch& s = it->second; ++wp_branches;
            uint64_t ft = s.pc + (s.len ? s.len : 4);
            uint64_t nxt = s.last_taken ? s.last_target : ft;
            if (is_call(s.kind)) ras->push(ft);
            else if (s.kind == K_RET) { uint64_t x; if (ras->pop(x) && x) nxt = x; }
            a = nxt;
        }
        ras->restore(cp);
    }

    void branch(const Rec& r, bool measure);
    Json report(uint64_t instructions) const;
};

// Micro-op cache: entries hold decoded ops of one aligned fetch window; a window
// with more ops than one line uses several lines of its set. A hit delivers ops at
// op_width per cycle and skips the I-cache and legacy decode. Owner-written.
class OpCache {
public:
    struct L { bool valid = false; uint64_t window = 0; unsigned part = 0; uint64_t stamp = 0; };
    std::vector<L> l; uint64_t sets; unsigned ways, ops_per_line, window_bits, max_lines, latency, switch_penalty, op_bits;
    double op_width; bool flush_on_context; uint64_t clock = 0;
    uint64_t lookups = 0, hits = 0, ops_hit = 0, ops_total = 0, fills = 0, uncacheable = 0, switches = 0, flushes = 0;
    explicit OpCache(const Config& c) {
        uint64_t entries = c.u("entries", 512, 1, 1u << 20); ways = unsigned(c.u("ways", 8, 1, 64));
        if (entries % ways || !pow2(entries / ways)) throw Error("op cache entries/ways must give a power-of-two set count");
        sets = entries / ways; ops_per_line = unsigned(c.u("ops_per_line", 6, 1, 64));
        uint64_t wb = c.u("window_bytes", 64, 4, 4096); if (!pow2(wb)) throw Error("op cache window_bytes must be a power of two");
        window_bits = log2u(wb); max_lines = unsigned(c.u("max_lines_per_window", 3, 1, 64));
        op_width = c.f("op_width", 8, 0.125, 64); latency = unsigned(c.u("latency", 1, 0, 100));
        switch_penalty = unsigned(c.u("switch_penalty", 1, 0, 100)); op_bits = unsigned(c.u("op_bits", 56, 8, 256));
        flush_on_context = c.choice("context", "flush", {"shared", "flush"}) == "flush";
        l.assign(entries, L());
    }
    L* find(uint64_t w, unsigned part) {
        L* s = &l[(w & (sets - 1)) * ways];
        for (unsigned k = 0; k < ways; ++k) if (s[k].valid && s[k].window == w && s[k].part == part) return &s[k];
        return nullptr;
    }
    unsigned need(uint64_t n) const { return unsigned((n + ops_per_line - 1) / ops_per_line); }
    bool lookup(uint64_t addr, uint64_t n, bool measure) {
        uint64_t w = addr >> window_bits; unsigned k = need(n);
        if (measure) { ++lookups; ops_total += n; }
        if (k > max_lines) return false;
        std::vector<L*> got;
        for (unsigned p = 0; p < k; ++p) { L* x = find(w, p); if (!x) return false; got.push_back(x); }
        for (L* x : got) x->stamp = ++clock;
        if (measure) { ++hits; ops_hit += n; }
        return true;
    }
    void fill(uint64_t addr, uint64_t n, bool measure) {
        uint64_t w = addr >> window_bits; unsigned k = need(n);
        if (k > max_lines || k > ways) { if (measure) ++uncacheable; return; }
        L* s = &l[(w & (sets - 1)) * ways];
        for (unsigned p = 0; p < k; ++p) {
            if (L* x = find(w, p)) { x->stamp = ++clock; continue; }
            L* v = &s[0];
            for (unsigned q = 0; q < ways; ++q) { if (!s[q].valid) { v = &s[q]; break; } if (s[q].stamp < v->stamp) v = &s[q]; }
            *v = L(); v->valid = true; v->window = w; v->part = p; v->stamp = ++clock; if (measure) ++fills;
        }
    }
    void context() { if (flush_on_context) { for (auto& x : l) x.valid = false; ++flushes; } }
    Storage storage() const { Storage s; s.add("ops", uint64_t(l.size()) * ops_per_line * op_bits); s.add("tags", uint64_t(l.size()) * (40 + 3 + log2u(ways))); return s; }
    Json stats() const {
        Json j = Json::object(); j["entries"] = uint64_t(l.size()); j["ways"] = ways; j["ops_per_line"] = ops_per_line;
        j["lookups"] = lookups; j["hits"] = hits; j["hit_rate"] = ratio(double(hits), double(lookups));
        j["ops_from_op_cache"] = ops_hit; j["op_coverage"] = ratio(double(ops_hit), double(ops_total));
        j["fills"] = fills; j["uncacheable_windows"] = uncacheable; j["mode_switches"] = switches; j["context_flushes"] = flushes;
        return j;
    }
};

// Decoupled front-end throughput model: a branch prediction unit fills a fetch target
// queue; fetch consumes it through the instruction cache; decode drains at a fixed
// width. Redirect latencies are fixed parameters. The back end never stalls.
class Frontend {
public:
    unsigned fetch_width, ftq_entries, decode_redirect, resolve_latency, bpu_to_fetch, fetch_to_decode;
    double preds_per_cycle, decode_width;
    bool fdip, wrong_path_icache;
    Cache* icache = nullptr; BranchStudy* bs = nullptr; std::unique_ptr<OpCache> opc; bool op_mode = false;
    double bpu_t = 0, dec_t = 0, redirect_t = 0, fetch_t = 0;
    std::deque<double> ftq;
    uint64_t prev_ord = 0, groups = 0, blocks = 0;
    double ftq_stall = 0, btb_bubbles = 0, icache_stall = 0, redirect_lost = 0, decode_redirect_lost = 0;
    double start_cycle = -1; uint64_t start_ord = 0; uint64_t wrong_path_lines = 0;
    uint64_t exec_redirects = 0, decode_redirects = 0;
    explicit Frontend(const Config& c) {
        fetch_width = unsigned(c.u("fetch_width", 8, 1, 64));
        preds_per_cycle = c.f("predictions_per_cycle", 1, 0.125, 16);
        ftq_entries = unsigned(c.u("ftq_entries", 32, 1, 4096));
        decode_width = c.f("decode_width", 4, 0.125, 64);
        decode_redirect = unsigned(c.u("decode_redirect_latency", 4, 0, 1000));
        resolve_latency = unsigned(c.u("resolve_latency", 12, 0, 1000));
        bpu_to_fetch = unsigned(c.u("bpu_to_fetch", 1, 0, 100));
        fetch_to_decode = unsigned(c.u("fetch_to_decode", 3, 0, 100));
        fdip = c.flag("fdip", false);
        wrong_path_icache = c.flag("wrong_path_icache", false);
        if (c.at("op_cache").any()) opc = std::make_unique<OpCache>(c.at("op_cache"));
    }
    template <class F> void lines(uint64_t a, uint64_t b, F f) {
        unsigned lb = icache ? icache->line_bits : 6;
        if (!a || a > b || b - a > 4096) a = b;
        for (uint64_t l = a >> lb; l <= (b >> lb); ++l) f(l);
    }
    void group(uint64_t first_pc, uint64_t last_pc, uint64_t n, bool ends_taken, int btb_level, bool measure) {
        double ftq_free = ftq.size() >= ftq_entries ? ftq.front() : 0;
        double ready = std::max(bpu_t, redirect_t);
        double start = std::max(ready, ftq_free);
        if (measure) ftq_stall += start - ready;
        bpu_t = start + 1.0 / preds_per_cycle;
        if (ends_taken && btb_level > 0 && bs && bs->btb) { double l = bs->btb->levels[size_t(btb_level)].latency; bpu_t += l; if (measure) btb_bubbles += l; }
        if (fdip && icache) lines(first_pc, last_pc, [&](uint64_t l) { icache->prefetch_into(l, last_pc, uint64_t(start)); });
        double fs = std::max(fetch_t, start + bpu_to_fetch);
        double done = fs;
        if (opc && first_pc) {
            bool hit = opc->lookup(first_pc, n, measure);
            if (hit != op_mode) { op_mode = hit; if (measure) ++opc->switches; dec_t = std::max(dec_t, fs) + opc->switch_penalty; }
            if (hit) {
                fetch_t = fs + 1;
                double ds = std::max(dec_t, fs + opc->latency);
                dec_t = ds + double(n) / opc->op_width;
                ftq.push_back(fs); while (ftq.size() > ftq_entries) ftq.pop_front();
                ++groups; return;
            }
            opc->fill(first_pc, n, measure);
        }
        if (icache) {
            uint64_t worst = 0;
            lines(first_pc, last_pc, [&](uint64_t l) { uint64_t d = icache->access(l << icache->line_bits, last_pc, uint64_t(fs), false, false, UINT64_MAX, nullptr); worst = std::max(worst, d); });
            double stall = std::max(0.0, double(worst) - (fs + icache->latency));
            done = fs + stall; if (measure) icache_stall += stall;
        }
        fetch_t = done + 1;
        double ds = std::max(dec_t, done + fetch_to_decode);
        dec_t = ds + double(n) / decode_width;
        ftq.push_back(done); while (ftq.size() > ftq_entries) ftq.pop_front();
        ++groups;
    }
    void block(const BranchOutcome& o, bool measure) {
        if (measure && start_cycle < 0) { start_cycle = dec_t; start_ord = prev_ord; }
        uint64_t n = o.ord - prev_ord; prev_ord = o.ord;
        ++blocks;
        uint64_t ngroups = (n + fetch_width - 1) / fetch_width;
        uint64_t first = o.block_start, last = o.pc + (o.len ? o.len : 4) - 1;
        for (uint64_t g = 0; g < ngroups; ++g) {
            uint64_t take = std::min<uint64_t>(fetch_width, n - g * fetch_width);
            bool final = g + 1 == ngroups;
            uint64_t a = first && first <= last ? first + (last - first + 1) * g / ngroups : last;
            uint64_t b = first && first <= last ? first + (last - first + 1) * (g + 1) / ngroups - 1 : last;
            group(a, final ? last : b, take, final && o.pred_taken, o.btb_level, measure);
        }
        if (o.exec_redirect) {
            double resolve = dec_t + resolve_latency;
            if (measure) { redirect_lost += std::max(0.0, resolve - bpu_t); ++exec_redirects; }
            if (wrong_path_icache && icache && bs) wrong_path_fetch(o.wrong_target, resolve);
            redirect_t = resolve; ftq.clear(); fetch_t = std::max(fetch_t, resolve);
        } else if (o.decode_redirect) {
            double r = fetch_t + decode_redirect;
            if (measure) { decode_redirect_lost += std::max(0.0, r - bpu_t); ++decode_redirects; }
            redirect_t = r; ftq.clear(); fetch_t = std::max(fetch_t, r);
        }
    }
    void wrong_path_fetch(uint64_t a, double until) {
        double t = fetch_t;
        for (int k = 0; k < 64 && a && t < until; ++k) {
            auto it = bs->cfg.find(a);
            if (it == bs->cfg.end()) break;
            const StaticBranch& s = it->second;
            lines(a, s.pc + 3, [&](uint64_t l) { icache->access(l << icache->line_bits, s.pc, uint64_t(t), false, false, UINT64_MAX, nullptr); ++wrong_path_lines; });
            t += 1;
            a = s.last_taken ? s.last_target : s.pc + (s.len ? s.len : 4);
        }
    }
    void finish(uint64_t total) {
        if (total > prev_ord) {
            uint64_t n = total - prev_ord, g = (n + fetch_width - 1) / fetch_width;
            for (uint64_t k = 0; k < g; ++k) group(0, 0, std::min<uint64_t>(fetch_width, n - k * fetch_width), false, -1, true);
            prev_ord = total;
        }
    }
    Json report(uint64_t) const {
        Json j = Json::object();
        double s = start_cycle < 0 ? 0 : start_cycle;
        double cycles = dec_t - s; uint64_t inst = prev_ord - start_ord;
        j["cycles"] = cycles; j["instructions"] = inst; j["delivered_ipc"] = ratio(double(inst), cycles);
        j["fetch_groups"] = groups; j["blocks"] = blocks;
        Json lost = Json::object();
        lost["ftq_full"] = ftq_stall; lost["btb_latency"] = btb_bubbles; lost["icache"] = icache_stall;
        lost["execute_redirects"] = redirect_lost; lost["decode_redirects"] = decode_redirect_lost;
        j["bubble_cycles"] = lost; j["execute_redirects"] = exec_redirects; j["decode_redirects"] = decode_redirects;
        j["fdip"] = fdip; j["wrong_path_icache_lines"] = wrong_path_lines;
        if (opc) { Json o = opc->stats(); o["storage"] = opc->storage().json(); j["op_cache"] = o; }
        Json p = Json::object();
        p["fetch_width"] = fetch_width; p["predictions_per_cycle"] = preds_per_cycle; p["ftq_entries"] = ftq_entries; p["decode_width"] = decode_width;
        p["decode_redirect_latency"] = decode_redirect; p["resolve_latency"] = resolve_latency;
        j["parameters"] = p;
        j["basis"] = "front-end delivery bound: the back end never stalls; redirect latencies are fixed; bubble categories can overlap";
        return j;
    }
};

inline void BranchStudy::branch(const Rec& r, bool measure) {
    if (measure) { counts[r.kind]++; taken_counts[r.kind] += r.taken; }
    bool pred_taken = true;  // unconditional branches are predicted taken
    bool dmiss = false, decode_redirect = false, exec_redirect = false; int level = -1;
    uint64_t wrong = 0, pred_target = 0, btb_target = 0;
    // --- direction
    if (r.kind == K_COND) {
        if (dir) {
            DirMeta m;
            dir->oracle(r.taken, r.target);
            dir->predict(r.pc, m);
            pred_taken = m.pred;
            dir->history(r.pc, r.kind, r.taken, r.target);
            queue.push_back({r.pc, r.taken, m});
            drain(delay);
            dmiss = m.pred != r.taken;
            if (dmiss) { exec_redirect = true; if (measure) ++dir_miss; }
        } else pred_taken = r.taken;
    } else if (dir) dir->history(r.pc, r.kind, r.taken, r.target);
    if (ind) ind->history(r.pc, r.kind, r.taken, r.target);
    // --- targets
    uint64_t ft = fallthrough(r);
    bool target_miss = false;
    if (btb || ras || ind) {
        if (!targets_available) throw Error("trace has no branch targets; target models need rvw.csim-trace/1 or champsim input");
        Btb::Hit h; if (btb) h = btb->lookup(r.pc);
        level = h.level; btb_target = h.level >= 0 ? h.target : 0;
        if (r.kind == K_RET && ras) {
            uint64_t a; bool ok = ras->pop(a);
            pred_target = ok ? a : btb_target;
            if (pred_target != r.target) { target_miss = true; exec_redirect = true; if (measure) ++ret_miss; }
        } else if (r.kind == K_IJUMP || r.kind == K_ICALL || r.kind == K_RET) {
            IndMeta im; bool used_ind = false;
            if (ind && ind->name() != "btb") { ind->predict(r.pc, im); used_ind = im.valid; }
            pred_target = used_ind ? im.pred : btb_target;
            if (ind) ind->update(r.pc, r.target, im);
            if (pred_target != r.target) { target_miss = true; exec_redirect = true; if (measure) ++ind_miss; }
        } else if (r.taken && pred_taken && btb) {
            pred_target = btb_target;
            if (h.level < 0) { decode_redirect = true; target_miss = true; if (measure) ++btb_miss; }
            else if (h.target != r.target) { decode_redirect = true; target_miss = true; if (measure) ++btb_wrong; }
        }
        if (is_call(r.kind) && ras && ft) ras->push(ft);
        if (btb) btb->update(r.pc, r.kind, r.taken, r.target);
    }
    // Unknown instruction lengths (ChampSim): learn each call site's size from its return.
    if (r.len == 0) {
        if (is_call(r.kind)) shadow.push_back(r.pc);
        else if (r.kind == K_RET && !shadow.empty()) {
            uint64_t c = shadow.back(); shadow.pop_back();
            if (r.target > c && r.target - c <= 15) call_size[c] = uint8_t(r.target - c);
        }
        if (shadow.size() > 4096) shadow.erase(shadow.begin());
    }
    if (exec_redirect) {
        wrong = dmiss ? (pred_taken ? btb_target : ft) : pred_target;
        wrong_path_walk(wrong);
    }
    if (measure && (r.kind == K_COND || target_miss || is_indirect(r.kind))) {
        PcStat& s = per_pc[r.pc]; s.kind = r.kind; ++s.execs; s.taken += r.taken; s.dir_miss += dmiss; s.target_miss += target_miss;
    }
    if (predictions.is_open() && measure)
        predictions << r.ord << ' ' << std::hex << r.pc << ' ' << kind_name(r.kind) << ' ' << r.taken << ' ' << pred_taken << ' '
                    << r.target << ' ' << pred_target << std::dec << '\n';
    if (learn_cfg && block_start) {
        StaticBranch& s = cfg[block_start]; s.pc = r.pc; s.kind = r.kind; s.len = r.len; s.last_taken = r.taken; if (r.taken) s.last_target = r.target;
    }
    if (fe) {
        BranchOutcome o{r.ord, r.pc, r.target, block_start, r.kind, r.len, r.taken, pred_taken, dmiss, decode_redirect, exec_redirect, level, wrong};
        fe->block(o, measure);
    }
    block_start = r.taken ? r.target : ft;
}

inline Json BranchStudy::report(uint64_t instructions) const {
    Json j = Json::object();
    Json counts_j = Json::object();
    uint64_t total = 0;
    for (int k = K_COND; k <= K_RET; ++k) { Json c = Json::object(); c["executed"] = counts[k]; c["taken"] = taken_counts[k]; counts_j[kind_name(k)] = c; total += counts[k]; }
    j["branches"] = total; j["by_kind"] = counts_j;
    if (dir) {
        Json d = Json::object();
        d["model"] = dir->name(); d["update_delay"] = delay;
        d["conditional"] = counts[K_COND]; d["misses"] = dir_miss; d["mpki"] = per_kilo(dir_miss, instructions);
        d["accuracy"] = counts[K_COND] ? Json(1.0 - double(dir_miss) / double(counts[K_COND])) : Json();
        d["storage"] = dir->storage().json(); d["internal"] = dir->stats();
        d["oracle_mpki"] = 0;
        j["direction"] = d;
    }
    Json t = Json::object();
    t["btb_misses_taken"] = btb_miss; t["btb_wrong_target"] = btb_wrong; t["indirect_misses"] = ind_miss; t["return_misses"] = ret_miss;
    t["decode_redirect_mpki"] = per_kilo(btb_miss + btb_wrong, instructions);
    t["indirect_mpki"] = per_kilo(ind_miss, instructions); t["return_mpki"] = per_kilo(ret_miss, instructions);
    t["target_mpki"] = per_kilo(btb_miss + btb_wrong + ind_miss + ret_miss, instructions);
    if (btb) { t["btb"] = btb->stats(); t["btb_storage"] = btb->storage().json(); }
    if (ras) { t["ras"] = ras->stats(); t["ras_storage"] = ras->storage().json(); }
    if (ind) { t["indirect_model"] = ind->name(); t["indirect"] = ind->stats(); t["indirect_storage"] = ind->storage().json(); }
    if (wrong_path) { Json w = Json::object(); w["branches_per_redirect"] = wrong_path; w["walked"] = wp_branches; w["stopped_unknown_block"] = wp_stops; t["wrong_path"] = w; }
    if (btb || ras || ind) j["target"] = t;
    j["execute_redirect_mpki"] = per_kilo(dir_miss + ind_miss + ret_miss, instructions);
    // Worst branches by mispredictions.
    std::vector<std::pair<uint64_t, PcStat>> v(per_pc.begin(), per_pc.end());
    std::sort(v.begin(), v.end(), [](auto& a, auto& b) {
        uint64_t x = a.second.dir_miss + a.second.target_miss, y = b.second.dir_miss + b.second.target_miss;
        return x != y ? x > y : a.first < b.first;
    });
    Json top = Json::array();
    for (size_t k = 0; k < v.size() && k < top_n; ++k) {
        Json e = Json::object(); std::ostringstream pc; pc << "0x" << std::hex << v[k].first;
        e["pc"] = pc.str(); e["kind"] = kind_name(v[k].second.kind); e["executed"] = v[k].second.execs; e["taken"] = v[k].second.taken;
        e["direction_misses"] = v[k].second.dir_miss; e["target_misses"] = v[k].second.target_miss; top.push(e);
    }
    j["top_branches"] = top; j["static_branches"] = uint64_t(per_pc.size());
    return j;
}

class MemoryStudy {
public:
    std::unique_ptr<Cache> l1i, l1d, l2, llc; std::unique_ptr<Mmu> mmu;
    double cpi = 1.0; bool active = false; bool l1d_opt = false;
    uint64_t block_start = 0;
    explicit MemoryStudy(const Config& c) {
        auto m = c.at("memory");
        if (!m.any() && !c.at("frontend").any()) return;
        active = m.any();
        cpi = m.f("cycles_per_instruction", 1.0, 0.0, 1000.0);
        uint64_t mem_lat = m.u("dram_latency", 200, 0, 100000);
        if (m.at("l2").any()) l2 = std::make_unique<Cache>("l2", m.at("l2"), 14, 1024, 8);
        if (m.at("llc").any()) llc = std::make_unique<Cache>("llc", m.at("llc"), 40, 8192, 16);
        if (m.at("l1d").any() || active) l1d = std::make_unique<Cache>("l1d", m.at("l1d"), 4, 48, 12);
        if (m.at("l1i").any() || c.at("frontend").any()) l1i = std::make_unique<Cache>("l1i", m.at("l1i"), 2, 64, 8);
        Cache* below_l1 = l2 ? l2.get() : llc.get();
        if (l2) l2->next = llc.get();
        for (Cache* x : {l1i.get(), l1d.get(), l2.get(), llc.get()}) if (x) x->memory_latency = mem_lat;
        if (l1d) l1d->next = below_l1;
        if (l1i) l1i->next = below_l1;
        if (m.at("tlb").any()) { mmu = std::make_unique<Mmu>(m.at("tlb")); mmu->cache = l1d.get(); }
        if (l1i && l1i->repl->name() == "opt") throw Error("opt replacement is supported on memory.l1d only");
        for (Cache* x : {l2.get(), llc.get()}) if (x && x->repl->name() == "opt") throw Error("opt replacement is supported on memory.l1d only");
        l1d_opt = l1d && l1d->repl->name() == "opt";
        if (l1d_opt && !l1d->pfs.empty()) throw Error("opt replacement cannot be combined with an l1d prefetcher");
    }
    void reset_stats() { for (Cache* x : {l1i.get(), l1d.get(), l2.get(), llc.get()}) if (x) reset(*x); if (mmu) reset(*mmu); }
    void data(const Rec& r, uint64_t next_use) {
        uint64_t t = uint64_t(double(r.ord) * cpi);
        if (mmu) t = mmu->translate(r.addr, r.pc, t);
        l1d->access(r.addr, r.pc, t, r.kind == K_STORE, false, next_use, nullptr);
    }
    // Instruction fetch lines of the block that ends at this branch (no front-end model).
    void fetch(const Rec& r) {
        if (!l1i) return;
        uint64_t t = uint64_t(double(r.ord) * cpi);
        uint64_t a = block_start, b = r.pc;
        if (!a || a > b || b - a > 4096) a = b;
        for (uint64_t l = a >> l1i->line_bits; l <= (b >> l1i->line_bits); ++l) l1i->access(l << l1i->line_bits, r.pc, t, false, false, UINT64_MAX, nullptr);
        block_start = r.taken ? r.target : r.pc + (r.len ? r.len : 4);
    }
    Json report(uint64_t instructions) const {
        Json j = Json::object(); Storage total;
        for (Cache* x : {l1i.get(), l1d.get(), l2.get(), llc.get()}) if (x) {
            Json s = x->stats(instructions); auto st = x->storage(); s["storage"] = st.json(); j[x->name] = s;
        }
        if (mmu) { Json s = mmu->stats(instructions); s["storage"] = mmu->storage().json(); j["tlb"] = s; }
        j["cycles_per_instruction"] = cpi;
        j["basis"] = "access time = ordinal * cycles_per_instruction; no bandwidth or MSHR limit for demand misses; prefetch timeliness uses these cycles";
        return j;
    }
};

}  // namespace csim
