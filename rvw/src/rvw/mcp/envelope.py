"""Additive C7 results. Preserve legacy fields and evidence limits."""
from rvw.common.verdicts import VERDICTS

# C4 decisions keep their meaning in the common vocabulary. Other legacy values stay inconclusive.
C4_VERDICTS = {"accept": "pass", "reject": "fail", "inconclusive": "inconclusive"}


def envelope(value, *, error=False):
    data = dict(value) if isinstance(value, dict) else {"result": value}
    old_verdict = data.get("verdict")
    verdict = old_verdict if old_verdict in VERDICTS else None
    # A completed command is not a verification pass.
    if verdict is None and data.get("status") in VERDICTS:
        verdict = data["status"]
    if error or data.get("error"):
        verdict = "not_installed" if data.get("code") == "not_installed" else "error"
    if old_verdict is not None and old_verdict not in VERDICTS:
        data["legacy_verdict"] = old_verdict
        c4 = str(data.get("schema", "")).startswith("rvw.verdict/") and not (error or data.get("error"))
        data["verdict"] = C4_VERDICTS.get(old_verdict, "inconclusive") if c4 else "inconclusive"
    elif verdict is not None:
        data["verdict"] = verdict
    evidence_status = data.get("verdict")
    default_status = evidence_status if evidence_status in VERDICTS - {"pass"} else "ok"
    data.setdefault("status", "error" if error or data.get("error") else default_status)
    data.setdefault("summary", str(data.get("error") or data.get("note") or "Command completed; inspect the returned evidence."))
    data.setdefault("artifacts", [])
    data.setdefault("next", ([{"tool": "job_status", "arguments": {"job_id": data["job_id"], "wait_s": 60}}]
                             if data.get("job_id") and data.get("status") not in ("done", "failed", "cancelled") else []))
    if data.get("error"):
        data.setdefault("code", "tool_error")
        data.setdefault("hint", "Use rvw_tools_describe to check arguments; inspect diagnostics before retrying.")
        data.setdefault("diagnostics", [{"code": data["code"], "message": str(data["error"]), "hint": data["hint"]}])
    data.setdefault("diagnostics", [])
    return data
