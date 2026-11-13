// Optional Verilator/SystemVerilog DPI client. Link this file into a harness.
// Send the C2 header first. Send irq/trap events before affected retirements.
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <string>
#include <regex>
#include <cstdio>
static int rvw_socket = -1;
extern "C" void rvw_cosim_close() {
  if (rvw_socket >= 0) close(rvw_socket);
  rvw_socket = -1;
}
// 0: continue, 1: complete match, 2: comparison stopped, -1: transport error.
// The full report is printed to stderr by the Python launcher/CLI.
extern "C" int rvw_cosim_observe(const char* c2) {
  if (rvw_socket < 0) {
    const char* port = std::getenv("RVW_COSIM_PORT");
    if (!port) return -1;
    rvw_socket = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(std::atoi(port));
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (connect(rvw_socket, (sockaddr*)&address, sizeof address)) {
      rvw_cosim_close(); return -1;
    }
  }
  std::string line = std::string(c2) + "\n";
  size_t sent = 0;
  while (sent < line.size()) {
    auto n = send(rvw_socket, line.data()+sent, line.size()-sent, 0);
    if (n <= 0) { rvw_cosim_close(); return -1; }
    sent += n;
  }
  std::string response;
  char c;
  while (recv(rvw_socket, &c, 1, 0) == 1) {
    if (c == '\n') {
      if (std::regex_search(response, std::regex(R"rx("status"\s*:\s*"continue")rx"))) return 0;
      std::fprintf(stderr, "%s\n", response.c_str());
      rvw_cosim_close();
      if (std::regex_search(response, std::regex(R"rx("status"\s*:\s*"match")rx")) &&
          std::regex_search(response, std::regex(R"rx("trace_complete"\s*:\s*true)rx"))) return 1;
      return 2;
    }
    response += c;
  }
  rvw_cosim_close(); return -1;
}
