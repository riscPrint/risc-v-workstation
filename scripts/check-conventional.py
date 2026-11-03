#!/usr/bin/env python3
"""Check new commit messages and PR titles against AGENTS.md."""
import json
import os
from pathlib import Path
import re
import subprocess

HEADER = re.compile(
    r"(?:feat|fix|docs|test|refactor|perf|build|ci|chore|revert)"
    r"\([a-z0-9][a-z0-9._/-]*\)(!)?: ([a-z0-9].*)"
)


def errors(message, *, title=False):
    lines = message.splitlines()
    match = HEADER.fullmatch(lines[0]) if lines else None
    if not match:
        return ["expected type(scope): lower case summary"]
    problems = []
    summary = match.group(2)
    if len(summary) > 72 or summary.endswith("."):
        problems.append("summary must have at most 72 characters and no final full stop")
    if not title:
        if not re.search(r"^(?:Refs|Closes): #\d+(?:[ ,]+#\d+)*$", message, re.M):
            problems.append("missing Refs: #N or Closes: #N footer")
        if match.group(1) and not re.search(r"^BREAKING CHANGE: .+", message, re.M):
            problems.append("missing BREAKING CHANGE: footer")
    return problems


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    pr = event.get("pull_request")
    failed = False
    if pr:
        for problem in errors(pr["title"], title=True):
            print(f"PR title: {problem}")
            failed = True
        head = pr["head"]["sha"]
        base = git("merge-base", pr["base"]["sha"], head)
    else:
        head = event["after"]
        base = event["before"]
        if base == "0" * 40:
            # A new branch has no push base. Its tip is the new commit.
            base = git("rev-parse", head + "^")
    commits = git("rev-list", "--no-merges", f"{base}..{head}").splitlines()
    for commit in commits:
        for problem in errors(git("show", "-s", "--format=%B", commit)):
            print(f"{commit}: {problem}")
            failed = True
    print(f"Checked {len(commits)} non-merge commit messages" + (" and PR title" if pr else ""))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
