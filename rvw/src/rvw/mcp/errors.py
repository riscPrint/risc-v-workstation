"""Machine-readable errors with inventory installation hints."""
from .envelope import envelope


def error_result(name, exc, arguments=None):
    from .spec import ToolError
    from jsonschema import ValidationError
    convert = getattr(exc, "to_json", None)
    data = dict(convert() if callable(convert) else getattr(exc, "data", {}) or {})
    code = getattr(exc, "code", None) or data.get("code")
    from rvw.doctor.inventory import load
    native = data.get("native_tool") or getattr(exc, "name", None) or getattr(exc, "filename", None)
    matches = [t for t in load()["tools"] if native and
               (native == t["name"] or any(native == p.get("module") or native in p.get("candidates", [])
                                           or native == p.get("name") for p in t["probes"]))]
    if not code:
        message = str(exc)
        code = ("unknown_tool" if message.startswith("unknown tool") else
                "invalid_arguments" if message.startswith("bad arguments") or isinstance(exc, (TypeError, ValidationError)) else
                "not_installed" if matches and isinstance(exc, (ModuleNotFoundError, FileNotFoundError)) else
                "invalid_input" if isinstance(exc, (FileNotFoundError, ValueError)) else
                "tool_error" if isinstance(exc, ToolError) or callable(convert) else "internal_error")
    hint = data.get("hint") or "Use rvw_tools_describe to check arguments; inspect diagnostics before retrying."
    if code == "not_installed":
        if matches:
            hint = "Run scripts/install.sh --with-" + matches[0]["flag"] + "; then retry."
        else:
            hint = "Run rvw doctor --json to identify the missing dependency; inspect its install_command."
    data.update(error=str(exc), code=code, hint=hint)
    result = envelope(data, error=True)
    if code == "not_installed":
        result["verdict"] = "not_installed"
        result["status"] = "not_installed"
    result["diagnostics"] = [{"code": code, "message": str(exc), "hint": hint}]
    result["next"] = []
    return result
