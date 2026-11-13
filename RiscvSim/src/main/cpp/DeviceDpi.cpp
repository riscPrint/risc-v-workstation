// Generic DPI-C entry points. Bind chandle in project SystemVerilog. Device
// signal names, memory maps and interrupt routing remain in project code.
#include "DevicePlugin.h"
extern "C" {
void* rvw_device_open(const char* library, const char* config, uint64_t seed) {
  try { return new riscvsim::DevicePlugin(library, config, seed); }
  catch (...) { return nullptr; }
}
void rvw_device_close(void* handle) {
  delete static_cast<riscvsim::DevicePlugin*>(handle);
}
int rvw_device_read(void* handle, uint64_t address, unsigned bytes, uint64_t* value) {
  if (!handle || !value || bytes == 0 || bytes > 8) return 1;
  try { *value = static_cast<riscvsim::DevicePlugin*>(handle)->read(address, bytes); return 0; }
  catch (...) { return 1; }
}
int rvw_device_write(void* handle, uint64_t address, unsigned bytes, uint64_t value, uint64_t mask) {
  if (!handle || bytes == 0 || bytes > 8) return 1;
  try { static_cast<riscvsim::DevicePlugin*>(handle)->write(address, bytes, value, mask); return 0; }
  catch (...) { return 1; }
}
int rvw_device_tick(void* handle, uint64_t cycle, uint64_t* interrupts) {
  if (!handle || !interrupts) return 1;
  try {
    auto* device = static_cast<riscvsim::DevicePlugin*>(handle);
    device->tick(cycle); *interrupts = device->interrupts(); return 0;
  } catch (...) { return 1; }
}
}
