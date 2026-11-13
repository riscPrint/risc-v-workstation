#pragma once
#include <cstdint>
#include <cstddef>
#include <dlfcn.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace riscvsim {
// Project libraries export rvw_device_plugin_v1. Calls are serialized by the
// harness at settled cycle boundaries. Addresses are device-relative bytes.
// The byte mask selects little-endian lanes. Models must never retain pointers
// to buffers passed by the harness. Nonzero status means failure.
// ABI 2 appends set_input: the harness drives one numbered device input (for
// example a PLIC gateway source) to a level. Hosts read it only when abi >= 2.
struct DeviceApiV1 {
  uint32_t abi;
  void* (*create)(const char* projectJson, uint64_t seed);
  void (*destroy)(void*);
  int (*read)(void*, uint64_t offset, uint32_t bytes, uint64_t* value);
  int (*write)(void*, uint64_t offset, uint32_t bytes, uint64_t value, uint64_t mask);
  int (*tick)(void*, uint64_t cycle);
  uint64_t (*interrupts)(void*);
  // snapshot(nullptr,0) returns the exact size. Zero means not restorable.
  size_t (*snapshot)(void*, uint8_t* destination, size_t capacity);
  int (*restore)(void*, const uint8_t* source, size_t size);
  int (*set_input)(void*, uint32_t input, uint32_t level);  // abi >= 2 only
};

class DevicePlugin {
  void* library = nullptr;
  const DeviceApiV1* api = nullptr;
  void* device = nullptr;
  static void checked(int status) {
    if (status) throw std::runtime_error("device plugin operation failed");
  }
public:
  DevicePlugin(const std::string& path, const std::string& config, uint64_t seed) {
    library = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (!library) throw std::runtime_error("cannot load device plugin: " + std::string(dlerror()));
    auto entry = reinterpret_cast<const DeviceApiV1* (*)()>(dlsym(library, "rvw_device_plugin_v1"));
    api = entry ? entry() : nullptr;
    if (!api || (api->abi != 1 && api->abi != 2) || (api->abi == 2 && !api->set_input) || !api->create || !api->destroy || !api->read ||
        !api->write || !api->tick || !api->interrupts || !api->snapshot || !api->restore) {
      dlclose(library); library = nullptr;
      throw std::runtime_error("unsupported device plugin ABI");
    }
    device = api->create(config.c_str(), seed);
    if (!device) {
      dlclose(library); library = nullptr;
      throw std::runtime_error("device plugin initialization failed");
    }
  }
  DevicePlugin(const DevicePlugin&) = delete;
  DevicePlugin& operator=(const DevicePlugin&) = delete;
  ~DevicePlugin() { if (device) api->destroy(device); if (library) dlclose(library); }
  uint64_t read(uint64_t offset, uint32_t bytes) {
    uint64_t value = 0; checked(api->read(device, offset, bytes, &value)); return value;
  }
  void write(uint64_t offset, uint32_t bytes, uint64_t value, uint64_t mask) {
    checked(api->write(device, offset, bytes, value, mask));
  }
  void tick(uint64_t cycle) { checked(api->tick(device, cycle)); }
  uint64_t interrupts() { return api->interrupts(device); }
  void setInput(uint32_t input, bool level) {
    if (api->abi < 2) throw std::runtime_error("device plugin has no inputs (ABI 1)");
    checked(api->set_input(device, input, level ? 1 : 0));
  }
  std::vector<uint8_t> snapshot() {
    const size_t size = api->snapshot(device, nullptr, 0);
    if (!size) throw std::runtime_error("device has non-restorable external effects");
    std::vector<uint8_t> state(size);
    if (api->snapshot(device, state.data(), size) != size)
      throw std::runtime_error("device snapshot size changed at stopped boundary");
    return state;
  }
  void restore(const std::vector<uint8_t>& state) {
    if (state.empty()) throw std::runtime_error("empty device snapshot");
    checked(api->restore(device, state.data(), state.size()));
  }
};
}
