#!/usr/bin/env bash
# No Spike source build. The add-on receives the captured primary shim API at runtime.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$here/build/libspike_replay.so}"
mkdir -p "$(dirname "$out")"
"${CXX:-c++}" -std=c++20 -O2 -fPIC -shared "$here/spike_replay.cc" -o "$out"
python3 - "$here/spike_replay.cc" "$out" <<'PY'
from pathlib import Path
from hashlib import sha256
import json,sys
source,target=map(Path,sys.argv[1:])
Path(str(target)+'.manifest.json').write_text(json.dumps(dict(schema='rvw.spike-replay-build/1',abi=1,
 source_sha256=sha256(source.read_bytes()).hexdigest(),library_sha256=sha256(target.read_bytes()).hexdigest()),indent=2)+'\n')
PY
