// Sequential, actual-path conditional direction models. No timing model.
#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static uint64_t number(const std::string& s, int base = 10) {
    if (s.empty() || s[0] == '-' || s[0] == '+') throw std::runtime_error("invalid integer");
    size_t end = 0;
    auto value = std::stoull(s, &end, base);
    if (end != s.size()) throw std::runtime_error("invalid integer");
    return value;
}
static void exhausted(std::istringstream& row) {
    std::string extra;
    if (row >> extra) throw std::runtime_error("extra field");
}
int main(int argc, char** argv) {
    try {
        if (argc > 6) throw std::runtime_error("usage: branch-sim [bimodal|gshare|perfect [entries [history_bits [pc_shift [warmup_instructions]]]]]");
        std::string model = argc > 1 ? argv[1] : "bimodal";
        if (model != "bimodal" && model != "gshare" && model != "perfect")
            throw std::runtime_error("unsupported model");
        uint64_t entries = argc > 2 ? number(argv[2]) : 4096;
        uint64_t history_bits = argc > 3 ? number(argv[3]) : 12;
        uint64_t shift = argc > 4 ? number(argv[4]) : 1;
        uint64_t warmup = argc > 5 ? number(argv[5]) : 0;
        if (!entries || entries > (1u << 24) || (entries & (entries-1)) || history_bits > 63 || shift > 63)
            throw std::runtime_error("invalid predictor configuration");
        std::string line, schema, count;
        if (!std::getline(std::cin, line)) throw std::runtime_error("missing header");
        std::istringstream header(line);
        if (!(header >> schema >> count) || schema != "rvw.branch-trace/1")
            throw std::runtime_error("invalid header");
        exhausted(header);
        uint64_t instructions = number(count);
        if (instructions <= warmup) throw std::runtime_error("empty measurement interval");
        std::vector<uint8_t> counters(entries, 1);
        uint64_t history = 0, previous = 0, branches = 0, misses = 0;
        uint64_t history_mask = (uint64_t(1) << history_bits) - 1;
        bool ended = false;
        while (std::getline(std::cin, line)) {
            if (line == "END") { ended = true; break; }
            std::istringstream row(line);
            std::string kind, ordinal_text, pc_text, taken_text;
            if (!(row >> kind >> ordinal_text >> pc_text >> taken_text) || kind != "B")
                throw std::runtime_error("invalid branch row");
            exhausted(row);
            uint64_t ordinal = number(ordinal_text), pc = number(pc_text, 16), taken = number(taken_text);
            if (ordinal <= previous || ordinal > instructions || taken > 1)
                throw std::runtime_error("invalid order or outcome");
            previous = ordinal;
            uint64_t index = ((pc >> shift) ^ (model == "gshare" ? history : 0)) & (entries-1);
            bool prediction = model == "perfect" ? bool(taken) : counters[index] >= 2;
            if (ordinal > warmup) { ++branches; misses += prediction != bool(taken); }
            auto& counter = counters[index];
            counter = taken ? std::min<int>(3, counter+1) : std::max<int>(0, counter-1);
            history = ((history << 1) | taken) & history_mask;
        }
        if (!ended) throw std::runtime_error("missing completion footer");
        if (std::getline(std::cin, line)) throw std::runtime_error("data after footer");
        if (std::cin.bad()) throw std::runtime_error("trace read failed");
        std::cout << std::setprecision(17)
                  << "{\"schema\":\"rvw.branch-sim/1\",\"status\":\"reported\",\"model\":\"" << model
                  << "\",\"entries\":" << entries << ",\"history_bits\":" << history_bits
                  << ",\"pc_shift\":" << shift << ",\"warmup_instructions\":" << warmup
                  << ",\"instructions\":" << instructions-warmup << ",\"branches\":" << branches
                  << ",\"direction_misses\":" << misses << ",\"mpki\":" << 1000.0*misses/(instructions-warmup)
                  << ",\"oracle_mpki\":0,\"training\":\"sequential-actual-path\",\"rtl_comparison\":\"inconclusive\"}\n";
    } catch (const std::exception& e) {
        std::cerr << "branch-sim: " << e.what() << '\n';
        return 2;
    }
}
