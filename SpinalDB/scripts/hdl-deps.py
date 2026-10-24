"""Run the Scala dependency scan with rvw's process-tree timeout and cancellation cleanup."""
import json
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rvw" / "src"))
from hdl_capture import execute


def cancel(signum, frame):
    # Selectors swallow InterruptedError; use an exception that reaches run_group cleanup.
    raise KeyboardInterrupt("SpinalDB dependency scan cancelled")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    if len(sys.argv) != 4 or sys.argv[1] != "--scan":
        sys.exit("usage: hdl-deps.py --scan REQUEST RESULT")
    request = json.loads(Path(sys.argv[2]).read_text())
    try:
        Path(sys.argv[3]).write_text(json.dumps(execute(request)))
    except KeyboardInterrupt:
        sys.exit(130)
