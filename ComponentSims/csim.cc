// csim: trace-driven component study driver.
//   csim CONFIG [--format csim|champsim] [--budget] [TRACE|-]
// CONFIG holds flat key=value lines (rvw csim writes it from a JSON study file).
// Exit 0 with a JSON report on stdout; exit 2 with a message on stderr on error.
#include <cstdio>
#include <fstream>
#include <iostream>
#include "csim/study.h"

using namespace csim;

struct Study {
    Config cfg;
    uint64_t warmup, limit;
    std::unique_ptr<BranchStudy> br; std::unique_ptr<MemoryStudy> mem; std::unique_ptr<Frontend> fe;
    std::unique_ptr<StoreSets> mdp; std::unique_ptr<ValuePredictor> vp; std::unique_ptr<AddressPredictor> lap;
    bool measuring = false; uint64_t last_ord = 0, contexts = 0;
    explicit Study(const Config& c) : cfg(c) {
        warmup = c.u("warmup_instructions", 0);
        limit = c.u("simulation_instructions", 0);
        br = std::make_unique<BranchStudy>(c);
        mem = std::make_unique<MemoryStudy>(c);
        if (c.at("frontend").any()) {
            fe = std::make_unique<Frontend>(c.at("frontend"));
            fe->icache = mem->l1i.get(); fe->bs = br.get(); br->fe = fe.get();
        }
        if (c.at("mdp").any()) mdp = std::make_unique<StoreSets>(c.at("mdp"));
        if (c.at("vp").any()) vp = std::make_unique<ValuePredictor>(c.at("vp"));
        if (c.at("lap").any()) lap = std::make_unique<AddressPredictor>(c.at("lap"));
        c.check_all_used();
        if (!br->active() && !mem->active && !fe && !mdp && !vp && !lap) throw Error("no component configured (branch, btb, ras, indirect, frontend, memory, mdp, vp or lap)");
    }
    Json storage() const {
        Json j = Json::object(); uint64_t total = 0, data = 0;
        auto add = [&](const char* n, const Storage& s) {
            j[n] = s.json(); total += s.bits();
            for (auto& p : s.parts) if (p.first == "data") data += p.second;
        };
        if (br->dir) add("direction", br->dir->storage());
        if (br->btb) add("btb", br->btb->storage());
        if (br->ras) add("ras", br->ras->storage());
        if (br->ind) add("indirect", br->ind->storage());
        for (Cache* x : {mem->l1i.get(), mem->l1d.get(), mem->l2.get(), mem->llc.get()}) if (x) add(x->name.c_str(), x->storage());
        if (mem->mmu) add("tlb", mem->mmu->storage());
        if (mdp) add("mdp", mdp->storage());
        if (vp) add("vp", vp->storage());
        if (lap) add("lap", lap->storage());
        j["total_bits"] = total; j["total_kib"] = double(total) / 8192.0;
        j["cache_data_kib"] = double(data) / 8192.0; j["metadata_kib"] = double(total - data) / 8192.0;
        return j;
    }
    // Returns false when the simulation limit is reached.
    bool step(const Rec& r, uint64_t next_use) {
        if (limit && r.ord > warmup + limit) return false;
        last_ord = r.ord;
        bool m = r.ord > warmup;
        if (m && !measuring) {
            measuring = true;
            mem->reset_stats();
            if (br->btb) reset(*br->btb);
            if (br->ras) reset(*br->ras);
        }
        if (is_branch(r.kind)) {
            if (br->active() || fe) br->branch(r, m);
            if (!fe && mem->l1i) mem->fetch(r);
            if (vp) vp->branch(r.kind, r.taken);
        } else if (r.kind == K_LOAD || r.kind == K_STORE) {
            if (mem->l1d && mem->active) mem->data(r, next_use);
            if (lap && r.kind == K_LOAD) lap->load(r.pc, r.addr, m);
            if (mdp) { if (r.kind == K_LOAD) mdp->load(r.ord, r.pc, r.addr, r.size, m); else mdp->store(r.ord, r.pc, r.addr, r.size, m); }
        } else if (r.kind == K_CONTEXT) {
            if (m) ++contexts;
            if (br->btb) br->btb->context(r.value);
            if (br->ras) br->ras->context();
            if (mem->mmu) mem->mmu->context(r.value);
        } else if (r.kind == K_VALUE) {
            if (vp) vp->value(r.pc, r.value, r.is_load, r.is_move, r.is_zero, m);
        }
        return true;
    }
    Json report(Reader& rd, bool limited) {
        uint64_t total = limited ? warmup + limit : rd.instructions();
        if (total <= warmup) throw Error("empty measurement interval");
        uint64_t measured = total - warmup;
        if (fe) fe->finish(total);
        Json j = Json::object();
        j["schema"] = "rvw.csim-report/1"; j["status"] = "reported";
        Json t = Json::object(); t["format"] = rd.format(); t["instructions"] = total; t["warmup_instructions"] = warmup;
        t["measured_instructions"] = measured; t["limited"] = limited; t["context_changes"] = contexts; j["trace"] = t;
        if (br->active()) j["branch"] = br->report(measured);
        if (fe) j["frontend"] = fe->report(measured);
        if (mem->active || mem->l1i) j["memory"] = mem->report(measured);
        if (mdp) j["mdp"] = mdp->stats(measured);
        if (lap) j["lap"] = lap->stats(measured);
        if (vp) { if (!rd.has_values()) throw Error("value prediction needs W rows; this trace format has none"); j["vp"] = vp->stats(measured); }
        j["storage"] = storage();
        j["training"] = "sequential-actual-path";
        j["rtl_comparison"] = "inconclusive";
        Json lim = Json::array();
        lim.push("actual-path trace: no wrong-path instructions except the learned-CFG walks that are configured");
        lim.push("MPKI and miss counts do not give IPC or speedup");
        j["limits"] = lim;
        return j;
    }
};

int main(int argc, char** argv) {
    try {
        std::string config_path, trace_path = "-", format = "csim"; bool budget = false;
        for (int k = 1; k < argc; ++k) {
            std::string a = argv[k];
            if (a == "--format" && k + 1 < argc) format = argv[++k];
            else if (a == "--budget") budget = true;
            else if (config_path.empty()) config_path = a;
            else if (trace_path == "-") trace_path = a;
            else throw Error("usage: csim CONFIG [--format csim|champsim] [--budget] [TRACE|-]");
        }
        if (config_path.empty()) throw Error("usage: csim CONFIG [--format csim|champsim] [--budget] [TRACE|-]");
        std::ifstream cf(config_path);
        if (!cf) throw Error("cannot read configuration");
        std::string text((std::istreambuf_iterator<char>(cf)), std::istreambuf_iterator<char>());
        Study s(Config::parse(text));
        if (budget) {
            Json j = Json::object(); j["schema"] = "rvw.csim-budget/1"; j["storage"] = s.storage();
            j.write(std::cout); std::cout << '\n'; return 0;
        }
        std::unique_ptr<Reader> rd; std::ifstream tf; std::FILE* bin = nullptr;
        if (format == "csim") {
            std::istream* in = &std::cin;
            if (trace_path != "-") { tf.open(trace_path); if (!tf) throw Error("cannot read trace"); in = &tf; }
            rd = std::make_unique<TextReader>(*in);
        } else if (format == "champsim") {
            bin = trace_path == "-" ? stdin : std::fopen(trace_path.c_str(), "rb");
            if (!bin) throw Error("cannot read trace");
            rd = std::make_unique<ChampSimReader>(bin);
        } else throw Error("unknown trace format");
        s.br->targets_available = rd->has_targets();
        Rec r; bool limited = false;
        if (s.mem->l1d_opt) {
            // Belady needs the future: buffer the trace and precompute next uses at l1d.
            std::vector<Rec> all; while (rd->next(r)) all.push_back(r);
            std::vector<uint64_t> next(all.size(), UINT64_MAX); std::unordered_map<uint64_t, uint64_t> seen;
            unsigned lb = s.mem->l1d->line_bits; uint64_t pos = 0; std::vector<uint64_t> apos(all.size(), 0);
            for (size_t k = 0; k < all.size(); ++k) if (all[k].kind == K_LOAD || all[k].kind == K_STORE) apos[k] = pos++;
            for (size_t k = all.size(); k-- > 0;) if (all[k].kind == K_LOAD || all[k].kind == K_STORE) {
                uint64_t l = all[k].addr >> lb; auto it = seen.find(l);
                next[k] = it == seen.end() ? UINT64_MAX : it->second; seen[l] = apos[k];
            }
            for (size_t k = 0; k < all.size(); ++k) if (!s.step(all[k], next[k])) { limited = true; break; }
        } else {
            while (rd->next(r)) if (!s.step(r, UINT64_MAX)) { limited = true; break; }
        }
        Json out = s.report(*rd, limited);
        if (bin && bin != stdin) std::fclose(bin);
        out.write(std::cout); std::cout << '\n';
    } catch (const std::exception& e) {
        std::cerr << "csim: " << e.what() << '\n';
        return 2;
    }
}
