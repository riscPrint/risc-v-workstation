"""`rvw` entry point. Each subpackage with a `cli.py` defining `register(subparsers)` adds its own
subcommand, so tools can be added without editing this file."""
import argparse
import importlib
import pkgutil
import signal
import sys
import threading

import rvw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rvw", description=rvw.__doc__)
    parser.add_argument("--version", action="version", version=rvw.__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    for mod in sorted(pkgutil.iter_modules(rvw.__path__), key=lambda m: m.name):
        if not mod.ispkg:
            continue
        try:
            cli = importlib.import_module(f"rvw.{mod.name}.cli")
        except ModuleNotFoundError as e:
            if e.name == f"rvw.{mod.name}.cli":
                continue
            raise
        cli.register(sub)
    def project_option(node):
        node.add_argument("--project", default=argparse.SUPPRESS,
                          help="project file or directory (default RVW_PROJECT or nearest rvw.toml)")
        for action in node._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    project_option(child)
    project_option(parser)
    from rvw.mcp.command_map import nodes
    for path, node in nodes(parser):
        # Native JSON handlers retain their documented schemas and exit codes.
        native_json = "--json" in node._option_string_actions
        if not native_json:
            node.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                              help="print a JSON result")
        node.set_defaults(_rvw_native_json=native_json)
        if path:
            required = []
            for action in node._actions:
                if isinstance(action, argparse._SubParsersAction) or action.dest in ("help", "project"):
                    continue
                if action.required:
                    flag = next((f for f in action.option_strings if f.startswith("--")), "")
                    required.extend(([flag] if flag else []) + ["<" + action.dest + ">"])
            example = "Example: rvw " + " ".join((*path, *required)) + " --json"
            node.epilog = (node.epilog + "\n" if node.epilog else "") + example
    return parser


class _SignalStop(KeyboardInterrupt):
    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(f"rvw stopped by signal {signum}")


def _stop(signum, frame):
    # Raise through run_group, then let each command's finally blocks release locks.
    raise _SignalStop(signum)


def main(argv=None) -> int:
    old = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGHUP):
            old[sig] = signal.signal(sig, _stop)
    try:
        args = build_parser().parse_args(argv)
        # Handlers resolve projects per invocation. Do not mutate process environment:
        # the same handlers also serve concurrent MCP calls.
        native_json = vars(args).pop("_rvw_native_json", True)
        if getattr(args, "json", False) and not native_json:
            from rvw.common.cli_json import execute
            return execute(args.func, args)
        if getattr(args, "json", False):
            try:
                return int(args.func(args) or 0)
            except Exception as exc:
                import json
                from rvw.mcp.errors import error_result
                print(json.dumps(error_result(args.command, exc)))
                return 2
        return int(args.func(args) or 0)
    except _SignalStop as exc:
        return 128 + exc.signum
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
