"""`rvw debug serve`: a remote_bitbang JTAG endpoint for a simulated debug target.

The target is the Debug Module reference model, or a core adapter's simulated
DMI bus (`dmi_process` transport) wrapped in the reference JTAG DTM. OpenOCD
attaches with `adapter driver remote_bitbang`; GDB attaches through OpenOCD.
"""
from __future__ import annotations

import threading
import time

from . import dm as dmmod, dmi as dmimod, jtag


class Endpoint:
    def __init__(self, profile, *, host='127.0.0.1', port=0, latency=0, idle=1, ticks_per_ms=50, log=None):
        kind = profile['transport']['kind']
        self.module = None
        if kind in ('model', 'jtag-model'):
            self.module = dmmod.DebugModule(profile)
            bus = dmmod.ModelBus(self.module)
            abits = 7
        elif kind == 'dmi_process':
            transport = profile['transport']
            bus = dmimod.ProcessBus(transport['command'], log=log, timeout=transport.get('timeout', 10),
                                    startup_timeout=transport.get('startup_timeout'))
            abits = bus.abits
        else:
            raise ValueError('serve needs a model or dmi_process transport; remote_bitbang targets already speak JTAG')
        self.bus = bus
        self.dtm = jtag.DTM(bus, abits=abits, idle=idle, latency=latency)
        self.server = jtag.BitbangServer(self.dtm, host, port)
        self.ticks_per_ms = ticks_per_ms
        self.stop_event = threading.Event()
        self.ticker = None

    @property
    def port(self):
        return self.server.port

    def start(self):
        self.server.start()
        if self.module is not None and self.ticks_per_ms:
            self.ticker = threading.Thread(target=self._tick, daemon=True)
            self.ticker.start()
        return self

    def _tick(self):
        # The hart keeps running between JTAG accesses, as a free-running simulation does.
        while not self.stop_event.wait(0.001):
            with self.server.lock:
                self.module.tick(self.ticks_per_ms)

    def stop(self):
        self.stop_event.set()
        self.server.stop()
        if self.ticker:
            self.ticker.join(2)
        close = getattr(self.bus, 'close', None)
        if close:
            close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def serve_forever(endpoint, *, duration=None, announce=print, port_file=None):
    endpoint.start()
    announce(f'Listening for remote bitbang connection on port {endpoint.port}.')
    if port_file:
        port_file.write_text(f'{endpoint.port}\n')
    try:
        deadline = None if duration is None else time.monotonic() + duration
        while deadline is None or time.monotonic() < deadline:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        endpoint.stop()
