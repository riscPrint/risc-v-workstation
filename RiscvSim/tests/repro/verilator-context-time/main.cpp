#include "Vclock_probe.h"
#include <iostream>
static double now = 0;
double sc_time_stamp() { return now; }
int main() { Vclock_probe dut; now = 17; dut.clk = 1; dut.eval(); std::cout << dut.hdl_time << "\n"; }
