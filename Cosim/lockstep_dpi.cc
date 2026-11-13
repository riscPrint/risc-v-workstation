// Optional Verilator/SystemVerilog DPI client. Link this file into a harness.
// Send the C2 header first. Send irq/trap events before affected retirements.
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <string>
#include <cctype>
#include <cstdio>
// Read one top-level scalar from the Python server's JSON object. Nested
// per-hart reports and reproduction data do not control this connection.
static std::string top_value(const std::string& json, const std::string& key) {
  unsigned depth = 0;
  auto skip_space = [&](size_t p) {
    while (p < json.size() && std::isspace(static_cast<unsigned char>(json[p]))) ++p;
    return p;
  };
  auto string_end = [&](size_t p) {
    for (++p; p < json.size(); ++p) {
      if (json[p] == '\\') ++p;
      else if (json[p] == '"') return p;
    }
    return json.size();
  };
  for (size_t p = 0; p < json.size(); ++p) {
    if (json[p] == '{' || json[p] == '[') ++depth;
    else if (json[p] == '}' || json[p] == ']') { if (depth) --depth; }
    else if (json[p] == '"') {
      size_t end = string_end(p);
      if (end == json.size()) return "";
      size_t colon = skip_space(end + 1);
      if (depth == 1 && json.substr(p, end-p+1) == "\"" + key + "\"" &&
          colon < json.size() && json[colon] == ':') {
        size_t start = skip_space(colon + 1), stop = start;
        if (start < json.size() && json[start] == '"') {
          stop = string_end(start);
          if (stop == json.size()) return "";
          ++stop;
        } else {
          while (stop < json.size() && json[stop] != ',' && json[stop] != '}' &&
                 !std::isspace(static_cast<unsigned char>(json[stop]))) ++stop;
        }
        return json.substr(start, stop-start);
      }
      p = end;
    }
  }
  return "";
}
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
      const auto status = top_value(response, "status");
      if (status == "\"continue\"") return 0;
      std::fprintf(stderr, "%s\n", response.c_str());
      rvw_cosim_close();
      if (status == "\"match\"" && top_value(response, "trace_complete") == "true") return 1;
      return 2;
    }
    response += c;
  }
  rvw_cosim_close(); return -1;
}
