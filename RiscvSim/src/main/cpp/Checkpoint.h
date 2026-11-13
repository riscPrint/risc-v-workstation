#pragma once
#include <verilated_save.h>
#include <stdexcept>
#include <string>

namespace riscvsim {
// The adapter must stop at a settled edge. Harness::transfer(Stream&) must
// serialize memory, devices, pending requests, RNG, monitors and C2 position.
// Do not serialize pointers, threads, sockets or host file descriptors.
template<class Model, class Harness> void save(
    const std::string& path, VerilatedContext& context, Model& model,
    Harness& harness, bool quiescent, bool externalEffects = false) {
  if (!quiescent || externalEffects)
    throw std::runtime_error("checkpoint requires a stopped restorable harness");
  VerilatedSave stream;
  stream.open(path.c_str());
  if (!stream.isOpen()) throw std::runtime_error("cannot open native checkpoint");
  stream << &context << model;
  harness.transfer(stream);
  stream.close();
}

template<class Model, class Harness> void restore(
    const std::string& path, VerilatedContext& context, Model& model,
    Harness& harness, bool quiescent, bool externalEffects = false) {
  if (!quiescent || externalEffects)
    throw std::runtime_error("restore requires a stopped restorable harness");
  // Validate the identity-bound envelope before this call. Discard this model
  // after any restore error. Verilator's native format is build dependent.
  VerilatedRestore stream;
  stream.open(path.c_str());
  if (!stream.isOpen()) throw std::runtime_error("cannot open native checkpoint");
  stream >> &context >> model;
  harness.transfer(stream);
  stream.close();
}
}
