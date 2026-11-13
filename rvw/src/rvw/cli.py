"""`rvw` entry point. Each subpackage with a `cli.py` defining `register(subparsers)` adds its own
subcommand, so tools can be added without editing this file."""
import argparse
import importlib
import pkgutil
import signal
import sys
import threading

import rvw


def _finish_parser(parser, path=()):
    """Add common options to a loaded command tree."""
    parser.add_argument("--project", default=argparse.SUPPRESS,
                        help="project file or directory (default RVW_PROJECT or nearest rvw.toml)")
    native_json = "--json" in parser._option_string_actions
    if not native_json:
        parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                            help="print a JSON result")
    parser.set_defaults(_rvw_native_json=native_json)
    if path:
        required = []
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction) or action.dest in ("help", "project"):
                continue
            if action.required:
                flag = next((f for f in action.option_strings if f.startswith("--")), "")
                required.extend(([flag] if flag else []) + ["<" + action.dest + ">"])
        example = "Example: rvw " + " ".join((*path, *required)) + " --json"
        parser.epilog = (parser.epilog + "\n" if parser.epilog else "") + example
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                if not isinstance(child, _LazyParser):
                    _finish_parser(child, (*path, name))


class _LazyParser(argparse.ArgumentParser):
    """Load one provider when argparse enters its command, or an inventory visits it."""
    def load(self):
        loader = getattr(self, "_loader", None)
        if loader is not None:
            loaded = loader()
            self._loader = None
            self.__dict__.update(loaded.__dict__)
        return self

    def parse_known_args(self, args=None, namespace=None):
        self.load()
        return super().parse_known_args(args, namespace)

    def format_help(self):
        self.load()
        return super().format_help()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rvw", description=rvw.__doc__)
    parser.add_argument("--version", action="version", version=rvw.__version__)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_LazyParser)
    for mod in sorted(pkgutil.iter_modules(rvw.__path__), key=lambda m: m.name):
        if not mod.ispkg:
            continue
        package = f"rvw.{mod.name}"
        try:
            declarations = importlib.import_module(f"{package}.cli_declarations")
        except ModuleNotFoundError as e:
            if e.name != f"{package}.cli_declarations":
                raise
            # Third-party providers can retain the original registration API.
            try:
                cli = importlib.import_module(f"{package}.cli")
            except ModuleNotFoundError as e:
                if e.name == f"{package}.cli":
                    continue
                raise
            cli.register(sub)
            continue
        loaded = {}
        def load(name, package=package, loaded=loaded):
            if not loaded:
                holder = argparse.ArgumentParser(prog="rvw")
                children = holder.add_subparsers()
                importlib.import_module(f"{package}.cli").register(children)
                for key, child in children.choices.items():
                    _finish_parser(child, (key,))
                loaded.update(children.choices)
            return loaded[name]
        for name, help_text in declarations.COMMANDS:
            child = sub.add_parser(name, help=help_text)
            child._loader = lambda name=name, load=load: load(name)
    _finish_parser(parser)
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
