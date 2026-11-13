// C ABI over the component models, for timing models that call them per event
// (for example rvw's OoO model through rvw.csim.lib). Build as a shared library:
//   c++ -std=c++17 -O2 -shared -fPIC -Iinclude capi.cc -o libcsim.so
// One handle holds the components a configuration describes (same keys as csim).
#include <cstring>
#include "csim/study.h"

using namespace csim;

namespace {
struct Handle {
    Config cfg; std::unique_ptr<BranchStudy> br; std::unique_ptr<MemoryStudy> mem;
    std::unordered_map<uint64_t, std::pair<uint64_t, DirMeta>> tickets; uint64_t next_ticket = 1;
    std::unordered_map<uint64_t, std::pair<uint64_t, IndMeta>> ind_tickets;
    std::string stats;
};
void fail(char* err, size_t len, const char* msg) { if (err && len) { std::strncpy(err, msg, len - 1); err[len - 1] = 0; } }
}

extern "C" {

void* csim_create(const char* config_kv, char* err, size_t errlen) {
    try {
        auto h = std::make_unique<Handle>();
        h->cfg = Config::parse(config_kv ? config_kv : "");
        h->br = std::make_unique<BranchStudy>(h->cfg);
        h->mem = std::make_unique<MemoryStudy>(h->cfg);
        h->cfg.check_all_used();
        return h.release();
    } catch (const std::exception& e) { fail(err, errlen, e.what()); return nullptr; }
}

void csim_destroy(void* p) { delete static_cast<Handle*>(p); }

// Direction: predict returns a ticket; update or discard it later (any order).
uint64_t csim_dir_predict(void* p, uint64_t pc, int* taken) {
    auto* h = static_cast<Handle*>(p);
    if (!h->br->dir) { *taken = 0; return 0; }
    DirMeta m; h->br->dir->predict(pc, m); *taken = m.pred;
    uint64_t t = h->next_ticket++; h->tickets.emplace(t, std::make_pair(pc, m)); return t;
}
int csim_dir_update(void* p, uint64_t ticket, int taken) {
    auto* h = static_cast<Handle*>(p);
    auto it = h->tickets.find(ticket); if (it == h->tickets.end()) return -1;
    h->br->dir->update(it->second.first, taken != 0, it->second.second); h->tickets.erase(it); return 0;
}
void csim_dir_discard(void* p, uint64_t ticket) { static_cast<Handle*>(p)->tickets.erase(ticket); }
// Advance global histories with one actual-path branch (kind: csim Kind values 1..6).
void csim_history(void* p, uint64_t pc, int kind, int taken, uint64_t target) {
    auto* h = static_cast<Handle*>(p);
    if (h->br->dir) h->br->dir->history(pc, kind, taken != 0, target);
    if (h->br->ind) h->br->ind->history(pc, kind, taken != 0, target);
}
int csim_btb_lookup(void* p, uint64_t pc, uint64_t* target) {
    auto* h = static_cast<Handle*>(p); if (!h->br->btb) return -1;
    auto r = h->br->btb->lookup(pc); *target = r.target; return r.level;
}
void csim_btb_update(void* p, uint64_t pc, int kind, int taken, uint64_t target) {
    auto* h = static_cast<Handle*>(p); if (h->br->btb) h->br->btb->update(pc, uint8_t(kind), taken != 0, target);
}
void csim_ras_push(void* p, uint64_t addr) { auto* h = static_cast<Handle*>(p); if (h->br->ras) h->br->ras->push(addr); }
int csim_ras_pop(void* p, uint64_t* addr) { auto* h = static_cast<Handle*>(p); if (!h->br->ras) return -1; return h->br->ras->pop(*addr) ? 1 : 0; }
uint64_t csim_ind_predict(void* p, uint64_t pc, uint64_t* target) {
    auto* h = static_cast<Handle*>(p); if (!h->br->ind) { *target = 0; return 0; }
    IndMeta m; h->br->ind->predict(pc, m); *target = m.valid ? m.pred : 0;
    uint64_t t = h->next_ticket++; h->ind_tickets.emplace(t, std::make_pair(pc, m)); return t;
}
int csim_ind_update(void* p, uint64_t ticket, uint64_t target) {
    auto* h = static_cast<Handle*>(p);
    auto it = h->ind_tickets.find(ticket); if (it == h->ind_tickets.end()) return -1;
    h->br->ind->update(it->second.first, target, it->second.second); h->ind_tickets.erase(it); return 0;
}
// Memory access at a caller cycle. Returns the completion cycle (0 if no such cache).
// fetch=1 uses the instruction path (l1i), otherwise translation (if any) then l1d.
uint64_t csim_mem_access(void* p, uint64_t cycle, uint64_t pc, uint64_t addr, int is_store, int fetch) {
    auto* h = static_cast<Handle*>(p); auto& m = *h->mem;
    if (fetch) return m.l1i ? m.l1i->access(addr, pc, cycle, false, false, UINT64_MAX, nullptr) : 0;
    if (!m.l1d) return 0;
    uint64_t t = m.mmu ? m.mmu->translate(addr, pc, cycle) : cycle;
    return m.l1d->access(addr, pc, t, is_store != 0, false, UINT64_MAX, nullptr);
}
void csim_reset_stats(void* p) {
    auto* h = static_cast<Handle*>(p); h->mem->reset_stats();
    if (h->br->btb) reset(*h->br->btb);
    if (h->br->ras) reset(*h->br->ras);
}
// JSON statistics and storage. Returns the required buffer length including NUL.
size_t csim_stats(void* p, uint64_t instructions, char* buf, size_t len) {
    auto* h = static_cast<Handle*>(p);
    Json j = Json::object();
    if (h->br->dir) { Json d = Json::object(); d["model"] = h->br->dir->name(); d["storage"] = h->br->dir->storage().json(); d["internal"] = h->br->dir->stats(); j["direction"] = d; }
    if (h->br->btb) { j["btb"] = h->br->btb->stats(); j["btb_storage"] = h->br->btb->storage().json(); }
    if (h->br->ras) j["ras"] = h->br->ras->stats();
    if (h->br->ind) j["indirect"] = h->br->ind->stats();
    if (h->mem->l1d || h->mem->l1i) j["memory"] = h->mem->report(instructions);
    h->stats = j.dump();
    if (buf && len) { std::strncpy(buf, h->stats.c_str(), len - 1); buf[len - 1] = 0; }
    return h->stats.size() + 1;
}

}  // extern "C"
