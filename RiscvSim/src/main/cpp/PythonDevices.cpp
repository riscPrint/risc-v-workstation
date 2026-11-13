// Optional CPython bridge to the deterministic standard models. ABI is unchanged.
#include "DevicePlugin.h"
#include <Python.h>
#include <cstring>
#include <mutex>
using namespace riscvsim;
namespace {
struct Gil { PyGILState_STATE state; Gil(): state(PyGILState_Ensure()) {} ~Gil(){PyGILState_Release(state);} };
PyObject* call(PyObject* p, const char* name, PyObject* args) {
  PyObject* method = PyObject_GetAttrString(p, name);
  PyObject* result = method ? PyObject_CallObject(method, args) : nullptr;
  Py_XDECREF(method); Py_DECREF(args);
  if (!result) PyErr_Print();
  return result;
}
// build-devices.py compiles in the interpreter home and the workstation's rvw/src. The
// interpreter is then isolated: no PYTHONHOME, PYTHONPATH or user site, so the library bytes
// (which embed both paths) identify the device runtime. Without the defines, the environment
// configures the embedded interpreter as before.
bool initialize() {
#if defined(RVW_DEVICE_PYTHON_HOME) && defined(RVW_DEVICE_PYTHON_PATH)
  PyConfig config;
  PyConfig_InitIsolatedConfig(&config);
  PyStatus status = PyConfig_SetBytesString(&config, &config.home, RVW_DEVICE_PYTHON_HOME);
  if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
  PyConfig_Clear(&config);
  if (PyStatus_Exception(status)) return false;
  PyObject* path = PySys_GetObject("path");
  PyObject* source = PyUnicode_FromString(RVW_DEVICE_PYTHON_PATH);
  bool ok = path && source && PyList_Insert(path, 0, source) == 0;
  Py_XDECREF(source);
  return ok;
#else
  Py_Initialize();
  return true;
#endif
}
void* create(const char* config, uint64_t seed) {
  static std::once_flag once;
  static bool ready = true;
  std::call_once(once, [] { if (!Py_IsInitialized()) { ready = initialize(); if (Py_IsInitialized()) PyEval_SaveThread(); } });
  if (!ready) return nullptr;
  Gil gil;
  PyObject* module = PyImport_ImportModule("rvw.sim.devices");
  PyObject* cls = module ? PyObject_GetAttrString(module, "Device") : nullptr;
  PyObject* result = cls ? PyObject_CallFunction(cls, "sK", config, seed) : nullptr;
  Py_XDECREF(cls); Py_XDECREF(module);
  if (!result) PyErr_Print();
  return result;
}
void destroy(void* p) { Gil gil; Py_DECREF(static_cast<PyObject*>(p)); }
int read(void* p, uint64_t off, uint32_t bytes, uint64_t* value) {
  Gil gil; auto r = call(static_cast<PyObject*>(p), "read", Py_BuildValue("(KI)", off, bytes));
  if (!r) return 1;
  *value = PyLong_AsUnsignedLongLong(r); Py_DECREF(r);
  if (PyErr_Occurred()) { PyErr_Print(); return 1; } return 0;
}
int write(void* p, uint64_t off, uint32_t bytes, uint64_t value, uint64_t mask) {
  Gil gil; auto r = call(static_cast<PyObject*>(p), "write", Py_BuildValue("(KIKK)", off, bytes, value, mask));
  if (!r) return 1; Py_DECREF(r); return 0;
}
int tick(void* p, uint64_t cycle) {
  Gil gil; auto r = call(static_cast<PyObject*>(p), "tick", Py_BuildValue("(K)", cycle));
  if (!r) return 1; Py_DECREF(r); return 0;
}
uint64_t irq(void* p) {
  Gil gil; auto r = call(static_cast<PyObject*>(p), "interrupts", PyTuple_New(0));
  if (!r) throw std::runtime_error("device interrupt evaluation failed");
  uint64_t result = PyLong_AsUnsignedLongLong(r); Py_DECREF(r);
  if (PyErr_Occurred()) { PyErr_Print(); throw std::runtime_error("device interrupt width exceeded"); }
  return result;
}
size_t snapshot(void* p, uint8_t* out, size_t capacity) {
  Gil gil; auto r = call(static_cast<PyObject*>(p), "snapshot", PyTuple_New(0));
  if (!r) return 0;
  char* data; Py_ssize_t length;
  if (PyBytes_AsStringAndSize(r, &data, &length)) { Py_DECREF(r); PyErr_Print(); return 0; }
  size_t size = static_cast<size_t>(length);
  if (out && capacity >= size) std::memcpy(out, data, size);
  else if (out) size = 0;
  Py_DECREF(r); return size;
}
int restore(void* p, const uint8_t* data, size_t size) {
  Gil gil;
  auto bytes = PyBytes_FromStringAndSize(reinterpret_cast<const char*>(data), size);
  auto args = PyTuple_Pack(1, bytes); Py_DECREF(bytes);
  auto r = call(static_cast<PyObject*>(p), "restore", args);
  if (!r) return 1; Py_DECREF(r); return 0;
}
}
extern "C" const DeviceApiV1* rvw_device_plugin_v1() {
  static const DeviceApiV1 api{1, create, destroy, read, write, tick, irq, snapshot, restore};
  return &api;
}
