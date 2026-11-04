"""One owned temporary directory per shard. No remote shell interpolation of inputs."""
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import json
from pathlib import Path
import shlex
import sys
import tempfile
import uuid
import time

from rvw.common.proc import run_group
from rvw.results import RunResult


def digest(data):
    return hashlib.sha256(data).hexdigest()


def worker(request, on_start=None):
    """Remote endpoint. Requires rvw installed in the host's selected Python."""
    deadline = time.monotonic() + request["timeout"]
    identity = run_group(request["identity_command"], capture=True, timeout=min(60, request["timeout"]), on_start=on_start)
    if identity.returncode or json.loads(identity.stdout) != request["identity"]:
        raise ValueError("remote tool identity differs")
    with tempfile.TemporaryDirectory(prefix="rvw-shard-") as temp:
        root = Path(temp)
        rows = []
        for i, cell in enumerate(request["cells"]):
            data = base64.b64decode(cell["elf_bytes"], validate=True)
            if digest(data) != cell["elf_sha256"]:
                raise ValueError("ELF transfer hash differs")
            elf = root / f"{i}.elf"
            elf.write_bytes(data)
            rows.append({**cell["options"], "elf": str(elf), "out": str(root / str(i))})
        manifest = root / "manifest.jsonl"
        manifest.write_text("".join(json.dumps(row) + "\n" for row in rows))
        r = run_group([*request["adapter"], "run-many", "--manifest", str(manifest),
                       "--jobs", str(request["jobs"])], timeout=max(.001, deadline - time.monotonic()), capture=True, on_start=on_start)
        cells = []
        for i, row in enumerate(rows):
            out = Path(row["out"])
            files = {}
            if out.exists():
                for p in out.rglob("*"):
                    if p.is_symlink():
                        raise ValueError("remote result contains a symlink")
                    if p.is_file():
                        data = p.read_bytes()
                        files[p.relative_to(out).as_posix()] = {"data": base64.b64encode(data).decode(), "sha256": digest(data)}
            cells.append({"id": request["cells"][i]["id"], "files": files})
        return {"identity": request["identity"], "returncode": r.returncode,
                "timed_out": r.timed_out, "cells": cells, "log": (r.stdout or "") + (r.stderr or "")}


def execute(hosts, manifest, adapter, identity_command, identity, out, *, jobs=1, timeout=600):
    if not hosts or jobs < 1 or timeout <= 0:
        raise ValueError("hosts, positive jobs and positive timeout are required")
    claims = identity.get("result_claims", {})
    if (identity.get("schema") != "rvw.adapter-capture/2" or not claims
            or not claims.get("tools.native_build.sha256") or claims.get("source.tools_dirty") is not False):
        raise ValueError("a complete /2 native tool identity with a clean harness is required")
    if len({h['name'] for h in hosts}) != len(hosts):
        raise ValueError("host names must be unique")
    for host in hosts:
        if host['address'].startswith('-'):
            raise ValueError("invalid SSH address")
        if host.get('resources', {}).get('cpu', jobs) < jobs:
            raise ValueError("CPU reservation must cover adapter jobs")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    rows = [json.loads(line) for line in Path(manifest).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("empty run-many manifest")
    cells = []
    for i, row in enumerate(rows):
        data = Path(row["elf"]).read_bytes()
        cells.append({"id": str(i), "options": {k: v for k, v in row.items() if k not in ("elf", "out")},
                      "elf_bytes": base64.b64encode(data).decode(), "elf_sha256": digest(data)})
    controls = [{"host": host, "token": uuid.uuid4().hex, "dispatched": i < len(cells)} for i, host in enumerate(hosts)]
    (out / "control.json").write_text(json.dumps(controls))
    def shard(index_host):
        index, host = index_host
        selected = cells[index::len(hosts)]
        result = {"host": host["name"], "expected_cells": [c["id"] for c in selected], "cells": [], "status": "inconclusive"}
        if not selected:
            return {**result, "status": "empty"}
        request = dict(cells=selected, adapter=adapter, identity_command=identity_command,
                       identity=identity, jobs=jobs, timeout=timeout, token=controls[index]["token"],
                       resources={"cpu": jobs, **host.get("resources", {})})
        try:
            address = host["address"]
            if address.startswith("-"):
                raise ValueError("invalid SSH address")
            cmd = ["ssh", "-oBatchMode=yes", "-oConnectTimeout=10", *host.get("ssh_options", []), address,
                   shlex.join([host.get("python", "python3"), "-m", "rvw.farm.worker"])]
            r = run_group(cmd, input=json.dumps(request), capture=True, timeout=timeout + 90)
            if r.returncode or r.timed_out:
                result["cancellation"] = cancel_host(controls[index])
                raise ValueError(f"SSH shard lost or aborted: exit {r.returncode}: {r.stderr}")
            reply = json.loads(r.stdout)
            result["reservation"] = reply.get("reservation")
            (out / f"shard-{index}.json").write_text(json.dumps(reply))
            if reply["identity"] != identity or reply["returncode"] or reply["timed_out"]:
                raise ValueError("shard identity or completion differs")
            if [c["id"] for c in reply["cells"]] != [c["id"] for c in selected]:
                raise ValueError("missing or duplicate shard cells")
            for sent, received in zip(selected, reply["cells"]):
                target = out / sent["id"]
                target.mkdir()
                for name, artifact in received["files"].items():
                    relative = Path(name)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("invalid artifact path")
                    data = base64.b64decode(artifact["data"], validate=True)
                    if digest(data) != artifact["sha256"]:
                        raise ValueError("artifact transfer hash differs")
                    p = target / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(data)
                run = RunResult.from_dict(json.loads((target / "result.json").read_text()))
                if run.config != sent["options"].get("config") or run.seed != sent["options"].get("seed"):
                    raise ValueError("result config or seed differs")
                for name in ("max_cycles", "mem_latency"):
                    if name in sent["options"]:
                        actual, wanted = getattr(run, name, None), sent["options"][name]
                        if type(actual) is not type(wanted) or actual != wanted:
                            raise ValueError(f"result {name} differs from requested value")
                if run.elf_sha256 != sent["elf_sha256"]:
                    raise ValueError("result ELF identity differs")
                raw = run.to_dict()
                def lookup(key):
                    value = raw
                    for part in key.split("."):
                        if not isinstance(value, dict) or part not in value:
                            raise ValueError("missing C1 identity claim")
                        value = value[part]
                    return value
                if any(lookup(key) != value for key, value in claims.items()):
                    raise ValueError("C1 identity claim differs")
                result["cells"].append({"id": sent["id"], "status": run.status,
                                         "inconclusive": run.why_inconclusive})
            result["status"] = "complete" if all(not c["inconclusive"] for c in result["cells"]) else "inconclusive"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["cause"] = str(exc)
        recorded = {c["id"] for c in result["cells"]}
        result["missing_cells"] = [c["id"] for c in selected if c["id"] not in recorded]
        return result
    pool = ThreadPoolExecutor(max_workers=len(hosts))
    try:
        shards = list(pool.map(shard, enumerate(hosts)))
    except BaseException:
        cancellation = [cancel_host(control) for control in controls]
        (out / "cancellation.json").write_text(json.dumps(cancellation, indent=2))
        raise
    finally:
        pool.shutdown(wait=True)
    report = {"schema": "rvw.farm/1", "expected_cells": len(cells), "plan": [{"id": c["id"], "options": c["options"], "elf_sha256": c["elf_sha256"]} for c in cells], "shards": shards,
              "status": "complete" if all(s["status"] in ("complete", "empty") for s in shards) else "inconclusive"}
    (out / "farm.json").write_text(json.dumps(report, indent=2))
    return report


def cancel_host(control):
    if not control.get("dispatched", True):
        return {"token": control["token"], "acknowledged": True, "cause": "no shard dispatched"}
    host = control["host"]
    command = ["ssh", "-oBatchMode=yes", "-oConnectTimeout=10", *host.get("ssh_options", []),
               host["address"], shlex.join([host.get("python", "python3"), "-m", "rvw.farm.worker", "--cancel", control["token"]])]
    try:
        reply = run_group(command, capture=True, timeout=30)
        if reply.returncode == 0:
            return json.loads(reply.stdout)
    except (OSError, ValueError):
        pass
    return {"token": control["token"], "acknowledged": False, "cause": "host unavailable or cleanup unconfirmed"}


def cancel(out):
    controls = json.loads((Path(out) / "control.json").read_text())
    results = [cancel_host(control) for control in controls]
    (Path(out) / "cancellation.json").write_text(json.dumps(results, indent=2))
    return {"status": "cancelled" if all(r["acknowledged"] for r in results) else "inconclusive", "shards": results}
