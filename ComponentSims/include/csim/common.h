// Shared helpers for the component models: configuration, JSON output,
// saturating counters, hashing and global/folded histories.
// Owner-written. No third-party source.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace csim {

struct Error : std::runtime_error { using std::runtime_error::runtime_error; };

// ---------------------------------------------------------------- JSON value
struct Json {
    enum Type { Null, Int, Num, Str, Bool, Obj, Arr } type = Null;
    int64_t i = 0; double d = 0; std::string s; bool b = false;
    std::vector<std::pair<std::string, Json>> o; std::vector<Json> a;
    Json() = default;
    Json(int v) : type(Int), i(v) {}
    Json(long v) : type(Int), i(v) {}
    Json(long long v) : type(Int), i(v) {}
    Json(unsigned v) : type(Int), i(v) {}
    Json(unsigned long v) : type(Int), i(int64_t(v)) {}
    Json(unsigned long long v) : type(Int), i(int64_t(v)) {}
    Json(double v) : type(Num), d(v) {}
    Json(bool v) : type(Bool), b(v) {}
    Json(const char* v) : type(Str), s(v) {}
    Json(std::string v) : type(Str), s(std::move(v)) {}
    static Json object() { Json j; j.type = Obj; return j; }
    static Json array() { Json j; j.type = Arr; return j; }
    Json& operator[](const std::string& k) {
        if (type != Obj) { type = Obj; o.clear(); }
        for (auto& kv : o) if (kv.first == k) return kv.second;
        o.emplace_back(k, Json());
        return o.back().second;
    }
    void push(Json v) { if (type != Arr) { type = Arr; a.clear(); } a.push_back(std::move(v)); }
    static void quote(std::ostream& out, const std::string& v) {
        out << '"';
        for (char c : v) {
            if (c == '"' || c == '\\') out << '\\' << c;
            else if (c == '\n') out << "\\n";
            else if (uint8_t(c) < 0x20) out << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << int(c) << std::dec;
            else out << c;
        }
        out << '"';
    }
    void write(std::ostream& out) const {
        switch (type) {
        case Null: out << "null"; break;
        case Int: out << i; break;
        case Num: if (std::isfinite(d)) out << std::setprecision(10) << d; else out << "null"; break;
        case Str: quote(out, s); break;
        case Bool: out << (b ? "true" : "false"); break;
        case Obj: {
            out << '{'; bool first = true;
            for (auto& kv : o) { if (!first) out << ','; first = false; quote(out, kv.first); out << ':'; kv.second.write(out); }
            out << '}'; break;
        }
        case Arr: {
            out << '['; for (size_t k = 0; k < a.size(); ++k) { if (k) out << ','; a[k].write(out); } out << ']'; break;
        }
        }
    }
    std::string dump() const { std::ostringstream s; write(s); return s.str(); }
};

inline double ratio(double a, double b) { return b ? a / b : 0.0; }
inline Json per_kilo(uint64_t events, uint64_t instructions) { return instructions ? Json(1000.0 * double(events) / double(instructions)) : Json(); }

// ---------------------------------------------------------------- configuration
// Flat key=value store. Every component reads its keys through a prefixed view.
// Keys that no component read are an error (unknown knobs are refused).
class Config {
    struct Store { std::map<std::string, std::string> kv; std::set<std::string> used; };
    std::shared_ptr<Store> st;
    std::string prefix;
public:
    Config() : st(std::make_shared<Store>()) {}
    static Config parse(const std::string& text) {
        Config c; std::istringstream in(text); std::string line;
        while (std::getline(in, line)) {
            if (line.empty() || line[0] == '#') continue;
            auto eq = line.find('=');
            if (eq == std::string::npos || eq == 0) throw Error("invalid configuration line: " + line);
            std::string k = line.substr(0, eq), v = line.substr(eq + 1);
            if (c.st->kv.count(k)) throw Error("duplicate configuration key: " + k);
            c.st->kv[k] = v;
        }
        return c;
    }
    void set(const std::string& k, const std::string& v) { st->kv[prefix + k] = v; }
    Config at(const std::string& sub) const { Config c = *this; c.prefix = prefix + sub + "."; return c; }
    Config at(const std::string& sub, size_t index) const { return at(sub + "." + std::to_string(index)); }
    std::string full(const std::string& k) const { return prefix + k; }
    bool has(const std::string& k) const { return st->kv.count(prefix + k) != 0; }
    bool any() const {  // any key under this prefix
        auto it = st->kv.lower_bound(prefix);
        return it != st->kv.end() && it->first.compare(0, prefix.size(), prefix) == 0;
    }
    size_t list(const std::string& sub) const {  // number of consecutive indexed children sub.0, sub.1 ...
        size_t n = 0; while (at(sub, n).any()) ++n; return n;
    }
    const std::string* raw(const std::string& k) const {
        auto it = st->kv.find(prefix + k);
        if (it == st->kv.end()) return nullptr;
        st->used.insert(it->first);
        return &it->second;
    }
    std::string str(const std::string& k, const std::string& def) const { auto v = raw(k); return v ? *v : def; }
    std::string need(const std::string& k) const { auto v = raw(k); if (!v) throw Error("missing configuration key: " + full(k)); return *v; }
    uint64_t u(const std::string& k, uint64_t def, uint64_t lo = 0, uint64_t hi = UINT64_MAX) const {
        auto v = raw(k);
        uint64_t x = def;
        if (v) {
            if (v->empty() || !std::all_of(v->begin(), v->end(), ::isdigit)) throw Error("invalid integer for " + full(k) + ": " + *v);
            try { x = std::stoull(*v); } catch (...) { throw Error("invalid integer for " + full(k)); }
        }
        if (x < lo || x > hi) throw Error("out of range: " + full(k) + "=" + std::to_string(x) + " (allowed " + std::to_string(lo) + ".." + std::to_string(hi) + ")");
        return x;
    }
    int64_t i(const std::string& k, int64_t def, int64_t lo, int64_t hi) const {
        auto v = raw(k);
        int64_t x = def;
        if (v) { try { size_t e; x = std::stoll(*v, &e); if (e != v->size()) throw 1; } catch (...) { throw Error("invalid integer for " + full(k)); } }
        if (x < lo || x > hi) throw Error("out of range: " + full(k));
        return x;
    }
    double f(const std::string& k, double def, double lo, double hi) const {
        auto v = raw(k);
        double x = def;
        if (v) { try { size_t e; x = std::stod(*v, &e); if (e != v->size()) throw 1; } catch (...) { throw Error("invalid number for " + full(k)); } }
        if (!(x >= lo && x <= hi)) throw Error("out of range: " + full(k));
        return x;
    }
    bool flag(const std::string& k, bool def) const {
        auto v = raw(k);
        if (!v) return def;
        if (*v == "true" || *v == "1") return true;
        if (*v == "false" || *v == "0") return false;
        throw Error("invalid boolean for " + full(k));
    }
    std::string choice(const std::string& k, const std::string& def, std::initializer_list<const char*> allowed) const {
        std::string v = str(k, def);
        for (auto a : allowed) if (v == a) return v;
        throw Error("unsupported value for " + full(k) + ": " + v);
    }
    std::vector<std::string> unused() const {
        std::vector<std::string> out;
        for (auto& kv : st->kv) if (!st->used.count(kv.first)) out.push_back(kv.first);
        return out;
    }
    void check_all_used() const {
        auto u = unused();
        if (!u.empty()) {
            std::string s; for (auto& k : u) s += (s.empty() ? "" : ", ") + k;
            throw Error("unknown configuration keys: " + s);
        }
    }
};

// ---------------------------------------------------------------- small utilities
inline bool pow2(uint64_t x) { return x && !(x & (x - 1)); }
inline unsigned log2u(uint64_t x) { unsigned n = 0; while ((uint64_t(1) << n) < x) ++n; return n; }
inline uint64_t mask(unsigned bits) { return bits >= 64 ? ~uint64_t(0) : (uint64_t(1) << bits) - 1; }
inline uint64_t mix64(uint64_t x) {  // splitmix64 finalizer
    x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL; x ^= x >> 27; x *= 0x94d049bb133111ebULL; x ^= x >> 31; return x;
}
struct Rng {  // deterministic xorshift64*
    uint64_t s;
    explicit Rng(uint64_t seed = 1) : s(seed ? seed : 1) {}
    uint64_t next() { s ^= s >> 12; s ^= s << 25; s ^= s >> 27; return s * 0x2545F4914F6CDD1DULL; }
    uint64_t below(uint64_t n) { return n ? next() % n : 0; }
};

// Signed saturating counter helpers. Range [-(2^(b-1)), 2^(b-1)-1].
inline int smax(unsigned bits) { return (1 << (bits - 1)) - 1; }
inline int smin(unsigned bits) { return -(1 << (bits - 1)); }
template <class T> inline void sat_update(T& c, bool up, int lo, int hi) {
    if (up) { if (c < hi) ++c; } else { if (c > lo) --c; }
}

// Global history bit buffer. bit(0) is the most recent bit.
class History {
    std::vector<uint8_t> buf; size_t head = 0, sz;
public:
    explicit History(size_t length = 64) : buf(std::max<size_t>(length + 1, 2), 0), sz(buf.size()) {}
    void push(bool b) { head = (head + sz - 1) % sz; buf[head] = b; }
    bool bit(size_t i) const { return i < sz ? buf[(head + i) % sz] : false; }
    size_t length() const { return sz - 1; }
    uint64_t low(unsigned n) const { uint64_t v = 0; for (unsigned k = 0; k < n && k < 64; ++k) v |= uint64_t(bit(k)) << k; return v; }
};

// Folded (compressed) history of the newest `length` bits into `width` bits.
// Update after History::push. Linear in the history bits.
struct Folded {
    uint64_t comp = 0; unsigned length = 0, width = 1, out = 0;
    Folded() = default;
    Folded(unsigned len, unsigned w) : length(len), width(std::max(1u, w)), out(len % std::max(1u, w)) {}
    void update(const History& h) {
        if (!length) return;
        comp = (comp << 1) ^ h.bit(0);
        comp ^= uint64_t(h.bit(length)) << out;
        comp ^= comp >> width;
        comp &= mask(width);
    }
};

// Branch and memory event kinds shared by trace readers and models.
enum Kind : uint8_t { K_NONE, K_COND, K_JUMP, K_IJUMP, K_CALL, K_ICALL, K_RET, K_LOAD, K_STORE, K_VALUE };
inline const char* kind_name(int k) {
    static const char* n[] = {"none", "cond", "jump", "ijump", "call", "icall", "ret", "load", "store", "value"};
    return n[k];
}
inline bool is_branch(int k) { return k >= K_COND && k <= K_RET; }
inline bool is_indirect(int k) { return k == K_IJUMP || k == K_ICALL || k == K_RET; }
inline bool is_call(int k) { return k == K_CALL || k == K_ICALL; }

// Storage accounting: named bit counts.
struct Storage {
    std::vector<std::pair<std::string, uint64_t>> parts;
    void add(const std::string& name, uint64_t bits) { parts.emplace_back(name, bits); }
    uint64_t bits() const { uint64_t t = 0; for (auto& p : parts) t += p.second; return t; }
    Json json() const {
        Json j = Json::object();
        j["bits"] = bits(); j["kib"] = double(bits()) / 8192.0;
        Json p = Json::object(); for (auto& x : parts) p[x.first] = x.second;
        j["parts"] = p; return j;
    }
};

}  // namespace csim
