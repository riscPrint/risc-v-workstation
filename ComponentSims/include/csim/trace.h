// Trace readers. Formats:
//   rvw.csim-trace/1  (native text, see README)
//   rvw.branch-trace/1 (legacy conditional-only text)
//   champsim          (public ChampSim 64-byte binary instruction records)
#pragma once
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <istream>
#include "common.h"

namespace csim {

struct Rec {
    uint64_t ord = 0;       // one-based instruction ordinal
    uint64_t pc = 0;
    uint8_t kind = K_NONE;
    bool taken = false;
    uint64_t target = 0;    // branch: actual next PC when taken (0 = unknown)
    uint8_t len = 4;        // instruction length in bytes (0 = unknown)
    uint64_t addr = 0;      // load/store address
    uint8_t size = 0;       // load/store bytes
    uint8_t rd = 0;         // value rows: destination register
    uint64_t value = 0;     // value rows: written value
    bool is_load = false, is_move = false, is_zero = false;  // value rows
};

class Reader {
public:
    virtual ~Reader() = default;
    // Returns false at the footer. Throws on malformed input.
    virtual bool next(Rec& r) = 0;
    // Total instruction count. Valid after next() returned false.
    virtual uint64_t instructions() const = 0;
    virtual bool has_targets() const { return true; }
    virtual bool has_values() const { return true; }
    virtual std::string format() const = 0;
};

inline uint64_t parse_u(const char* s, int base, const char* what) {
    if (!*s || *s == '-' || *s == '+') throw Error(std::string("invalid ") + what);
    char* end = nullptr; errno = 0;
    uint64_t v = std::strtoull(s, &end, base);
    if (errno || *end) throw Error(std::string("invalid ") + what + ": " + s);
    return v;
}

inline int split(char* line, char** f, int max) {
    int n = 0;
    for (char* p = std::strtok(line, " \t\r"); p && n < max; p = std::strtok(nullptr, " \t\r")) f[n++] = p;
    return n;
}

class TextReader : public Reader {
    std::istream& in;
    bool legacy = false, ended = false;
    uint64_t declared = 0, total = 0, last = 0, last_branch = 0;
    std::string line;
    uint64_t lineno = 1;
    void fail(const std::string& m) const { throw Error("trace line " + std::to_string(lineno) + ": " + m); }
public:
    explicit TextReader(std::istream& s) : in(s) {
        if (!std::getline(in, line)) throw Error("missing trace header");
        std::vector<char> b(line.begin(), line.end()); b.push_back(0);
        char* f[4]; int n = split(b.data(), f, 4);
        if (n == 2 && !std::strcmp(f[0], "rvw.branch-trace/1")) { legacy = true; declared = parse_u(f[1], 10, "instruction count"); }
        else if (n == 1 && !std::strcmp(f[0], "rvw.csim-trace/1")) legacy = false;
        else throw Error("invalid trace header");
    }
    std::string format() const override { return legacy ? "rvw.branch-trace/1" : "rvw.csim-trace/1"; }
    bool has_targets() const override { return !legacy; }
    bool has_values() const override { return !legacy; }
    uint64_t instructions() const override { return total; }
    bool next(Rec& r) override {
        if (ended) return false;
        while (std::getline(in, line)) {
            ++lineno;
            if (line.empty() || line[0] == '#') continue;
            std::vector<char> b(line.begin(), line.end()); b.push_back(0);
            char* f[9]; int n = split(b.data(), f, 9);
            r = Rec();
            if (!std::strcmp(f[0], "END")) {
                if (legacy) { if (n != 1) fail("invalid footer"); total = declared; }
                else { if (n != 2) fail("invalid footer"); total = parse_u(f[1], 10, "instruction count"); }
                if (total < last) fail("instruction count below last ordinal");
                ended = true;
                if (std::getline(in, line)) { ++lineno; fail("data after footer"); }
                return false;
            }
            if (n < 2) fail("short row");
            r.ord = parse_u(f[1], 10, "ordinal");
            if (r.ord == 0 || r.ord < last) fail("ordinals must be positive and non-decreasing");
            if (legacy) {
                if (n != 4 || std::strcmp(f[0], "B")) fail("invalid branch row");
                if (r.ord <= last_branch || r.ord > declared) fail("invalid order");
                r.pc = parse_u(f[2], 16, "pc"); r.kind = K_COND;
                uint64_t t = parse_u(f[3], 10, "direction"); if (t > 1) fail("invalid direction");
                r.taken = t; r.target = 0;
            } else if (!std::strcmp(f[0], "B")) {
                if (n != 6 && n != 7) fail("invalid branch row");
                if (r.ord <= last_branch) fail("two branches at one ordinal");
                r.pc = parse_u(f[2], 16, "pc");
                std::string k = f[3];
                if (k == "cond") r.kind = K_COND; else if (k == "jump") r.kind = K_JUMP; else if (k == "ijump") r.kind = K_IJUMP;
                else if (k == "call") r.kind = K_CALL; else if (k == "icall") r.kind = K_ICALL; else if (k == "ret") r.kind = K_RET;
                else fail("unknown branch kind " + k);
                uint64_t t = parse_u(f[4], 10, "direction"); if (t > 1) fail("invalid direction");
                r.taken = t; r.target = parse_u(f[5], 16, "target");
                if (r.kind != K_COND && !r.taken) fail("unconditional branch must be taken");
                if (n == 7) { r.len = uint8_t(parse_u(f[6], 10, "length")); if (r.len > 15) fail("invalid length"); }
                last_branch = r.ord;
            } else if (!std::strcmp(f[0], "L") || !std::strcmp(f[0], "S")) {
                if (n != 5) fail("invalid memory row");
                r.kind = f[0][0] == 'L' ? K_LOAD : K_STORE;
                r.pc = parse_u(f[2], 16, "pc"); r.addr = parse_u(f[3], 16, "address");
                uint64_t s = parse_u(f[4], 10, "size"); if (!s || s > 64) fail("invalid access size"); r.size = uint8_t(s);
            } else if (!std::strcmp(f[0], "W")) {
                if (n != 6) fail("invalid value row");
                r.kind = K_VALUE; r.pc = parse_u(f[2], 16, "pc");
                uint64_t rd = parse_u(f[3], 10, "register"); if (rd > 63) fail("invalid register"); r.rd = uint8_t(rd);
                r.value = parse_u(f[4], 16, "value");
                std::string fl = f[5];
                if (fl != "-") for (char c : fl) {
                    if (c == 'l') r.is_load = true; else if (c == 'm') r.is_move = true; else if (c == 'z') r.is_zero = true;
                    else fail("invalid value flag");
                }
            } else fail(std::string("unknown row type ") + f[0]);
            last = r.ord;
            return true;
        }
        if (in.bad()) throw Error("trace read failed");
        throw Error("missing completion footer");
    }
};

// ChampSim binary records (public trace format): ip, is_branch, branch_taken,
// 2 destination registers, 4 source registers, 2 destination and 4 source memory
// addresses. Branch type follows the documented register-usage rules.
class ChampSimReader : public Reader {
    std::FILE* in;
    struct Raw { uint64_t ip; uint8_t is_branch, taken, dreg[2], sreg[4]; uint64_t dmem[2], smem[4]; };
    static_assert(sizeof(uint64_t) == 8, "");
    Raw cur{}, nxt{};
    bool have_cur = false, have_next = false, done = false;
    uint64_t count = 0;
    std::vector<Rec> pending; size_t pos = 0;
    bool read_raw(Raw& r) {
        unsigned char b[64];
        size_t got = std::fread(b, 1, 64, in);
        if (got == 0) return false;
        if (got != 64) throw Error("truncated ChampSim record");
        std::memcpy(&r.ip, b, 8); r.is_branch = b[8]; r.taken = b[9];
        std::memcpy(r.dreg, b + 10, 2); std::memcpy(r.sreg, b + 12, 4);
        std::memcpy(r.dmem, b + 16, 16); std::memcpy(r.smem, b + 32, 32);
        return true;
    }
    static int classify(const Raw& r) {
        const int SP = 6, FLAGS = 25, IP = 26;
        bool rsp = false, wsp = false, rfl = false, rip = false, wip = false, roth = false;
        for (auto x : r.sreg) { if (x == SP) rsp = true; else if (x == FLAGS) rfl = true; else if (x == IP) rip = true; else if (x) roth = true; }
        for (auto x : r.dreg) { if (x == SP) wsp = true; if (x == IP) wip = true; }
        if (!wip) return K_NONE;
        if (!rsp && !rfl && !roth && !wsp) return K_JUMP;
        if (!rsp && !rip && !rfl && roth) return K_IJUMP;
        if (!rsp && rip && !wsp && rfl && !roth) return K_COND;
        if (rsp && rip && wsp && !rfl && !roth) return K_CALL;
        if (rsp && rip && wsp && !rfl && roth) return K_ICALL;
        if (rsp && !rip && wsp) return K_RET;
        return K_IJUMP;  // "other" branch: treat as indirect
    }
public:
    explicit ChampSimReader(std::FILE* f) : in(f) {}
    std::string format() const override { return "champsim"; }
    bool has_values() const override { return false; }
    uint64_t instructions() const override { return count; }
    bool next(Rec& out) override {
        while (pos >= pending.size()) {
            pending.clear(); pos = 0;
            if (done) return false;
            if (!have_cur) { if (!read_raw(cur)) { done = true; return false; } have_cur = true; }
            have_next = read_raw(nxt);
            ++count;
            int kind = cur.is_branch ? classify(cur) : K_NONE;
            if (cur.is_branch && kind == K_NONE) kind = K_COND;  // marked branch without IP write: conditional
            for (auto a : cur.smem) if (a) { Rec r; r.ord = count; r.pc = cur.ip; r.kind = K_LOAD; r.addr = a; r.size = 8; pending.push_back(r); }
            for (auto a : cur.dmem) if (a) { Rec r; r.ord = count; r.pc = cur.ip; r.kind = K_STORE; r.addr = a; r.size = 8; pending.push_back(r); }
            if (kind != K_NONE) {
                Rec r; r.ord = count; r.pc = cur.ip; r.kind = uint8_t(kind); r.len = 0;
                r.taken = kind == K_COND ? cur.taken != 0 : true;
                if (r.taken) {
                    if (!have_next) { /* final taken branch without successor: drop the target */ r.target = 0; }
                    else r.target = nxt.ip;
                }
                pending.push_back(r);
            }
            if (have_next) cur = nxt; else { have_cur = false; done = true; }
        }
        out = pending[pos++];
        return true;
    }
};

}  // namespace csim
