"""CLI JSON fallback for commands without their own machine-readable output."""
import contextlib
import io
import json


def execute(func, args):
    from rvw.mcp.envelope import envelope
    from rvw.mcp.errors import error_result
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            rc = int(func(args) or 0)
        text = stream.getvalue()
        try:
            data = json.loads(text)
        except ValueError:
            data = {"output": text}
        result = envelope(data)
        if rc == 2:
            result.update(status="error", verdict="error")
        elif rc == 3:
            result["verdict"] = "inconclusive"
        elif rc == 1 and isinstance(data, dict) and "status" in data and "output" not in data:
            # Exit 1 is a finding (fail, mismatch, violation). Keep the command's
            # own status, such as a security violation, and mark the verdict fail.
            result["verdict"] = "fail"
        elif rc:
            result["status"] = "error"
            result.setdefault("code", "command_failed")
        print(json.dumps(result, default=str))
        return rc
    except Exception as exc:
        print(json.dumps(error_result(getattr(args, "command", ""), exc)))
        return 2
