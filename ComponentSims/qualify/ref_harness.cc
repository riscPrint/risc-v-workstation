// Runs a CBP 2016 PREDICTOR (external, not in this repository) over an
// rvw.csim-trace/1 file and writes rvw.csim-predictions/1 rows for conditional
// branches. Build with -I<shim> -I<reference predictor directory>.
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include "predictor.h"

int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: ref-harness TRACE PREDICTIONS\n"; return 2; }
    std::ifstream in(argv[1]); std::ofstream out(argv[2]);
    std::string line;
    if (!std::getline(in, line) || line != "rvw.csim-trace/1") { std::cerr << "ref-harness: bad header\n"; return 2; }
    out << "rvw.csim-predictions/1\n";
    PREDICTOR& p = *new PREDICTOR();  // heap: unlimited predictors overflow the stack
    unsigned long long branches = 0, misses = 0;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream r(line); std::string kind; r >> kind;
        if (kind == "END") break;
        if (kind != "B") continue;
        unsigned long long ord; std::string pcs, k, tgs; int taken;
        r >> ord >> pcs >> k >> taken >> tgs;
        UINT64 pc = std::stoull(pcs, nullptr, 16), tgt = std::stoull(tgs, nullptr, 16);
        if (k == "cond") {
            bool pred = p.GetPrediction(pc);
            p.UpdatePredictor(pc, OPTYPE_JMP_DIRECT_COND, taken != 0, pred, tgt);
            ++branches; misses += pred != (taken != 0);
            out << ord << ' ' << std::hex << pc << " cond " << taken << ' ' << pred << ' ' << tgt << ' ' << 0 << std::dec << '\n';
        } else {
            OpType op = k == "jump" ? OPTYPE_JMP_DIRECT_UNCOND : k == "ijump" ? OPTYPE_JMP_INDIRECT_UNCOND :
                        k == "call" ? OPTYPE_CALL_DIRECT_UNCOND : k == "icall" ? OPTYPE_CALL_INDIRECT_UNCOND : OPTYPE_RET_UNCOND;
            p.TrackOtherInst(pc, op, true, tgt);
        }
    }
    std::cerr << "ref-harness: " << branches << " conditional, " << misses << " misses\n";
    return 0;
}
