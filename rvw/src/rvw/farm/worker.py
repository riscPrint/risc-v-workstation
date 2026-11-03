import json
import signal
import sys
from .executor import worker

def stop(signum, frame):
    raise KeyboardInterrupt("remote shard cancelled")

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    print(json.dumps(worker(json.load(sys.stdin))))
