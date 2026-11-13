"""Generate command inventory from argparse and the workflow playbook."""
import argparse


def nodes(parser, path=()):
    yield path, parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield from nodes(child, (*path, name))


def command_map():
    from rvw.cli import build_parser
    from rvw.agent.guide import load
    commands = []
    for path, parser in nodes(build_parser()):
        if not path:
            continue
        flags = sorted({f for a in parser._actions for f in a.option_strings})
        commands.append({"command": "rvw " + " ".join(path), "options": flags,
                         "examples": [parser.epilog] if parser.epilog else []})
    workflows = [{"id": w["id"], "steps": [{"cli": s.get("cli"), "mcp": s.get("mcp")}
                   for s in w["steps"] if s.get("cli")]} for w in load()["workflows"]]
    return {"schema": "rvw.command-map/1", "workflows": workflows, "commands": commands}
