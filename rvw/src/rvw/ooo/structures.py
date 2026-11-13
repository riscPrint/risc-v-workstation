"""Core-independent timing policies and effective-configuration evidence."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path


class StaticPredictor:
    """Predict sequential execution. Replace via the simulate predictor argument."""

    def predict(self, pc, fallthrough):
        return fallthrough

    def update(self, pc, actual_next):
        pass


def check_configuration(config, path):
    """Check all modeled settings against a project-owned extraction snapshot.

    This checks the exported data. It does not execute elaboration or establish
    that the exporting adapter read the selected RTL revision correctly.
    """
    data = Path(path).read_bytes()
    snapshot = json.loads(data)
    if snapshot.get("schema") != "rvw.ooo-effective/1":
        raise ValueError("unsupported effective configuration schema")
    revision = snapshot.get("source_revision")
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("effective configuration requires a full source revision")
    if not snapshot.get("config"):
        raise ValueError("effective configuration requires a selected config")
    expected = asdict(config)
    actual = snapshot.get("parameters")
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("effective configuration drift: " + ", ".join(
            key for key in expected if not isinstance(actual, dict) or actual.get(key) != expected[key]))
    sources = snapshot.get("extraction_keys", {})
    if set(sources) != set(expected) or any(not isinstance(v, str) or not v.strip() for v in sources.values()):
        raise ValueError("extraction_keys must identify every modeled field")
    # Required hardware structures with no model equivalent cannot be hidden.
    supported = {"integer", "branches", "ports", "registers", "address_disambiguation"}
    required = snapshot.get("required_structures", [])
    if not isinstance(required, list) or any(x not in supported for x in required):
        raise ValueError("unsupported required timing structure")
    return dict(sha256=sha256(data).hexdigest(), source_revision=revision,
                config=snapshot["config"], extraction_keys=sources,
                limits=["exported snapshot only; elaboration not verified"])
