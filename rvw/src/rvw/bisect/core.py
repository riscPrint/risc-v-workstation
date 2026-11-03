"""Find the core commit that introduced a failure signature.

Works on a private clone of the core repository (never the shared checkout), driven step by step
with `git bisect good|bad|skip`. At each revision the run's adapter command is executed with the
core-source environment variable (BOOM: SPINAL_BOOM) pointing at a captured copy of that revision:

    signature matches        -> bad
    run passes               -> good
    wall-clock timeout       -> skip, always (the adapter's `timeout:wall-clock` or rvw's --timeout:
                                inconclusive, says nothing about the revision)
    anything else            -> skip (build failure, other failure); --other good|bad changes that

The endpoints are checked first (bad must match, good must not), unless --no-verify.

Workspace safety: the default workspace is a new, uniquely named directory under
~/.cache/rvw/bisect; it is locked (flock) for the whole bisect so no two bisects share it. An
existing --workdir is used only if it is a real directory (not a link) holding this tool's marker
and its own independent git clone of the same origin; anything else is refused. Every git command on
the clone names its --git-dir and --work-tree explicitly, after checking that the clone is that
private clone, so a checkout can never act on another repository. --remove-clone deletes the clone
only if this invocation created it.

Max cycles: --max-cycles, else the original run's max cycles when RUN_DIR is a trial of an
`rvw reduce` (found through ../reduce.json), else the run's own. A reduced run's tight max cycles
would stop a good revision before the program ends (a timeout, not a pass). If the good endpoint
times out, the error says to pass a larger --max-cycles. A `timeout` counts as the signature only
with hang evidence (RVFI trace, --hang-cycles), as in `rvw reduce`.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path

from .. import runs
from ..common.jsonout import say
from ..runs import adapter
from ..runs.inputs import DebugInputs
from ..common.capture import run_git
from ..common.capture import Capture, CaptureError
from ..results.generation import open_current
from ..runs.hang import validate_hang_cycles, hang_check

MARK = ".rvw-bisect.json"


@dataclass
class Options:
    good: str
    bad: str | None = None
    core_repo: str | None = None
    core_env: str | None = None
    workdir: Path | None = None
    signature: str | None = None
    other: str = "skip"
    verify: bool = True
    keep: bool = True
    max_steps: int = 40
    timeout: float | None = None
    max_cycles: int | None = None
    hang_cycles: int = 5000
    project: str | None = None


class Bisector:
    def __init__(self, run_dir: str, o: Options):
        o = replace(o)
        validate_hang_cycles(o.hang_cycles)
        self.o = o
        self.inputs = DebugInputs()
        self.run = runs.open_run(run_dir, capture=self.inputs.capture)
        self.sig = o.signature or runs.signature(self.run.data)
        if self.sig == "pass":
            raise ValueError("the run passed; nothing to bisect")
        if self.run.inconclusive and not o.signature:
            raise ValueError(f"the run is inconclusive ({self.run.inconclusive}); re-run the test alone, "
                             "or pass --signature")
        if runs.inconclusive(self.sig):
            raise ValueError(f"the signature is a wall-clock timeout ({self.sig}): machine load or a hung "
                             "process, not a core failure; re-run the test with a longer timeout, or pass "
                             "--signature")
        cfg, _ = self.inputs.config(self.run.get("core"), project=o.project)
        self.env_var = o.core_env or (cfg.get("core") or {}).get("source_env")
        if not self.env_var:
            raise ValueError("unknown core source variable: pass --core-env (BOOM: SPINAL_BOOM) or set "
                             "[core].source_env in the core debug description")
        src = self.run.get("source") or {}
        self.origin = Path(o.core_repo or src.get("core_repo") or self.inputs.environment.get(self.env_var, "")).absolute()
        if not (self.origin / ".git").exists():
            raise ValueError(f"core repo {self.origin} is not a git checkout (pass --core-repo)")
        self.bad = o.bad or src.get("core_rev") or "HEAD"
        self.good = self.inputs.capture.git_ref(self.origin, o.good)
        self.badrev = self.inputs.capture.git_ref(self.origin, self.bad)
        self.origin = Path(next(ref['resolved'] for ref in self.inputs.record()['git_refs']
                                if ref['source'] == str(self.origin)))
        self.git_tool = str(self.inputs.capture.tool('git').path)
        self.base: Path | None = None
        self.clone: Path | None = None
        self.created_clone = False
        self._lockf = None
        self.steps: list[dict] = []
        self.source_captures = {}
        self.commands = {}
        self.cmd = self.inputs.command(self.run, cfg, source=False)
        self.max_cycles, self.max_cycles_from = self._max_cycles()
        self.cmd = self.cmd.set(max_cycles=self.max_cycles)
        if runs.signature_matches("timeout", self.sig):
            self.cmd = self.cmd.set(rvfi_trace=True)

    def _max_cycles(self) -> tuple[int | None, str]:
        if self.o.max_cycles:
            return int(self.o.max_cycles), "--max-cycles"
        rj = self.run.dir.parent / "reduce.json"
        if (rj.parent / "current").exists() or (rj.parent / "current").is_symlink():
            generation = open_current(rj.parent)
            raw = generation.read_bytes("reduce.json")
            saved = self.inputs.capture.root.parent / (self.inputs.capture.root.name + "-reduce.json")
            saved.write_bytes(raw)
            rj = saved
            self.parent_generation = generation.id
        if rj.exists():
            try:
                rep = json.loads(self.inputs.capture.file(rj).copy.read_text())
                mine = any(Path(t.get("dir", "")).resolve() == self.run.dir for t in rep.get("trials", []))
                orig = (rep.get("original") or {}).get("max_cycles")
                if mine and orig:
                    return int(orig), f"the unreduced run ({rj})"
            except CaptureError:
                raise
            except (OSError, ValueError, TypeError):
                pass
        mc = self.run.get("max_cycles")
        return (int(mc) if mc else None), "the run"

    # --- workspace ---------------------------------------------------------------------------

    def _workspace(self) -> None:
        """Create or validate the workspace, and lock it for this invocation."""
        if self.o.workdir:
            base = Path(self.o.workdir).absolute()
            if base.is_symlink():
                raise ValueError(f"--workdir {base} is a symbolic link; give a real directory")
            if base.exists():
                if not base.is_dir():
                    raise ValueError(f"--workdir {base} is not a directory")
                if any(base.iterdir()):
                    self._check_own(base)
            else:
                base.mkdir(parents=True)
        else:
            root = Path.home() / ".cache" / "rvw" / "bisect"
            root.mkdir(parents=True, exist_ok=True)
            base = Path(tempfile.mkdtemp(prefix=f"{self.run.get('core') or 'core'}-"
                                         f"{time.strftime('%Y%m%d-%H%M%S')}-", dir=root))
        self.base = base.resolve()
        self.clone = self.base / "core"
        self._lockf = open(self.base / ".lock", "w")
        try:
            fcntl.flock(self._lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lockf.close()
            self._lockf = None
            raise ValueError(f"{self.base} is in use by another rvw bisect") from None
        mark = self.base / MARK
        if not mark.exists():
            mark.write_text(json.dumps({"origin": str(self.origin)}) + "\n")

    def _check_own(self, base: Path) -> None:
        mark = base / MARK
        try:
            origin = json.loads(mark.read_text()).get("origin")
        except (OSError, ValueError):
            raise ValueError(f"--workdir {base} exists and is not an rvw bisect workspace "
                             f"(no {MARK}); give a new or empty directory") from None
        if origin != str(self.origin):
            raise ValueError(f"--workdir {base} belongs to a bisect of {origin}, not {self.origin}")
        if (base / "core").exists() or (base / "core").is_symlink():
            self._verify_clone(base / "core")

    def _verify_clone(self, clone: Path) -> None:
        """Refuse anything but this tool's own private clone of the origin."""
        bad = f"{clone} is not a private clone of {self.origin}; refusing to touch it"
        if clone.is_symlink() or not clone.is_dir():
            raise ValueError(bad + " (a link or not a directory)")
        gd = clone / ".git"
        if gd.is_symlink() or not gd.is_dir():
            raise ValueError(bad + " (no .git directory of its own)")
        top = self._git(clone, "rev-parse", "--show-toplevel", check=False)
        url = self._git(clone, "config", "--get", "remote.origin.url", check=False)
        if not top or Path(top).resolve() != clone.resolve() or not url or Path(url).resolve() != self.origin:
            raise ValueError(bad + f" (top level {top!r}, origin {url!r})")
        if (gd / 'objects/info/alternates').exists():
            raise CaptureError('input_not_captured:history',
                               'the workspace borrows live git objects; use a new --workdir')
        if clone.resolve() == self.origin:
            raise ValueError(bad + " (it is the origin itself)")

    def _git(self, clone: Path, *args, check=True) -> str:
        p = self._git_run(clone, *args)
        if check and p.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
        return (p.stdout or '').strip()

    def _git_run(self, clone, *args):
        result = run_git(clone, f"--git-dir={clone / '.git'}", f"--work-tree={clone}",
                         *args, tool=self.git_tool, env=self.inputs.environment, timeout=60)
        if result.timed_out:
            raise RuntimeError('git timed out (process group stopped)')
        return result

    def g(self, *args, check=True) -> str:
        """git on the private clone only (explicit --git-dir/--work-tree, never discovery)."""
        return self._git(self.clone, *args, check=check)

    def say(self, m):
        say("bisect", m)

    def prepare(self):
        self._workspace()
        self.report_dir = adapter.fresh_dir(self.base / "reports")
        if not (self.clone.exists() or self.clone.is_symlink()):
            self.say(f"cloning {self.origin} -> {self.clone}")
            # Captured: nothing git prints may reach stdout, which holds the --json document.
            p = run_git(None, "clone", "--quiet", "--no-hardlinks", "--dissociate", "--no-checkout",
                        str(self.origin), str(self.clone), tool=self.git_tool,
                        env=self.inputs.environment, timeout=60)
            if p.timed_out or p.returncode != 0:
                raise RuntimeError(f"git clone {self.origin}: {(p.stderr or p.stdout).strip()}")
            self.created_clone = True
        self._verify_clone(self.clone)
        # Every later operation names the IDs resolved before cloning.
        self.g('cat-file', '-e', f'{self.good}^{{commit}}')
        self.g('cat-file', '-e', f'{self.badrev}^{{commit}}')

    def test(self, rev: str, label: str) -> dict:
        self._verify_clone(self.clone)
        self.g('clean', '-ffdx')
        self.g("checkout", "--quiet", "--force", rev)
        if rev not in self.source_captures:
            capture = Capture(self.inputs.capture.root / f'revision-{rev}')
            rev = capture.git_ref(self.clone, rev)
            source = capture.tree(self.clone)
            self.inputs.allow_build_outputs(source)
            self.source_captures[rev] = (capture, source)
        source_capture, source = self.source_captures[rev]
        subj = self.g("log", "-1", "--format=%h %s", rev)
        out = self.base / "runs" / f"{len(self.steps):02d}-{rev[:10]}"
        c = self.cmd.set()
        c.env[self.env_var] = str(source.copy)
        c = self.inputs.launcher_command(c, source, revision=rev)
        self.replay = c
        self.commands[rev] = c
        at = adapter.execute(c, out, core=self.run.get("core"), timeout=self.o.timeout)
        r, wall, out = at.run, at.wall, at.dir
        s = runs.signature(r.data) if r else ("wall-timeout" if at.timed_out else "no-result")
        note = None
        if r is not None and r.inconclusive:
            verdict, note = "skip", f"inconclusive: {r.inconclusive}"
        elif r is not None and runs.signature_matches(s, self.sig):
            verdict = "bad"
            if s == "timeout":
                hung, note = hang_check(r, self.o.hang_cycles)
                if hung is None:
                    verdict = "skip"   # no hang evidence: inconclusive whatever --other says
                elif not hung:
                    verdict = self.o.other
        elif r is not None and s == "pass":
            verdict = "good"
        elif at.error and 'input_not_captured:' in at.error:
            verdict, note = 'skip', at.error
        elif at.timed_out:
            verdict = "skip"           # the wall clock ran out: inconclusive whatever --other says
        else:
            verdict = self.o.other
        step = {"label": label, "rev": rev, "commit": subj, "signature": s, "verdict": verdict,
                "cycles": r.get("cycles") if r else None, "wall_s": round(wall, 1),
                "lock_wait_s": round(at.lock_wait, 1), "dir": str(out),
                "source_capture": source_capture.record(), "source_sha256": source.sha256,
                "capture": r.capture.record() if r is not None and r.capture is not None else None,
                "replay": c.set(out='OUT_DIR').shell()}
        if note:
            step["hang"] = note
        self.steps.append(step)
        self.say(f"{label} {subj}: {s} -> {verdict}" + (f" ({note})" if note else ""))
        self.save()
        return step

    def bisect(self) -> dict:
        try:
            self.prepare()
            return self._bisect()
        finally:
            if self._lockf is not None:
                self._lockf.close()
                self._lockf = None

    def _bisect(self) -> dict:
        result: dict = {}
        try:
            if self.o.verify:
                b = self.test(self.badrev, "bad?")
                if b["verdict"] != "bad":
                    result = {"inconclusive": b["verdict"] == "skip",
                              "error": f"the bad revision does not reproduce {self.sig} (got {b['signature']})"}
                    return self.save(result)
                g = self.test(self.good, "good?")
                if g["verdict"] != "good":
                    hint = (f"it reached max cycles {self.max_cycles} ({self.max_cycles_from}); if the program "
                            f"needs more, pass a larger --max-cycles" if g["signature"] == "timeout"
                            else "the endpoint was skipped; use a compatible adapter or revision"
                            if g["verdict"] == "skip" else "pick an older one")
                    result = {"inconclusive": g["verdict"] == "skip",
                              "error": f"the good revision is not good (got {g['signature']}); {hint}"}
                    return self.save(result)
            self.g("bisect", "reset", check=False)
            outp = self.g("bisect", "start", self.badrev, self.good)
            for _ in range(self.o.max_steps):
                m = re.search(r"([0-9a-f]{40}) is the first '?bad'? commit", outp)
                if m:
                    result = self._found(m.group(1))
                    break
                if "There are only 'skip'ped commits left" in outp:
                    revs = re.findall(r"^([0-9a-f]{40})$", outp, re.M)
                    result = {"ambiguous": revs, "note": "only skipped commits left; the first bad commit is one of these"}
                    break
                rev = self.g("rev-parse", "HEAD")
                if any(st["rev"] == rev and st["label"] == "step" for st in self.steps):
                    result = {"error": f"git bisect did not advance past {rev[:10]}: {outp.strip()[:300]}"}
                    break
                step = self.test(rev, "step")
                p = self._git_run(self.clone, "bisect", step["verdict"])
                outp = p.stdout + p.stderr
            else:
                result = {"error": "max steps reached"}
            result["log"] = self.g("bisect", "log", check=False)
        finally:
            self.g("bisect", "reset", check=False)
        if not self.o.keep:
            if self.created_clone:
                self._verify_clone(self.clone)
                shutil.rmtree(self.clone)
                result["clone_removed"] = True
            else:
                result["clone_removed"] = False
                self.say(f"not removing {self.clone}: this invocation did not create it")
        return self.save(result)

    def _found(self, rev: str) -> dict:
        rev = self.inputs.capture.git_ref(self.clone, rev)
        if rev in self.commands:
            self.replay = self.commands[rev]
        show = self.g("show", "--stat", "--format=%H%n%an <%ae>%n%ad%n%n%B", rev)
        self.say(f"first bad commit: {self.g('log', '-1', '--format=%h %s', rev)}")
        return {"first_bad": rev, "commit": self.g("log", "-1", "--format=%h %s", rev), "show": show, "replay_tested": rev in self.commands}

    def save(self, result: dict | None = None) -> dict:
        rep = {"schema": "rvw.bisect/1", "run": str(self.run.dir), "signature": self.sig,
               "core_repo": str(self.origin), "workdir": str(self.base), "clone": str(self.clone), "good": self.good, "bad": self.badrev,
               "command": getattr(self, "replay", self.cmd).set(out="OUT_DIR").shell(), "env": self.env_var,
               "max_cycles": self.max_cycles, "max_cycles_from": self.max_cycles_from,
               "steps": self.steps, "result": result or {}, "capture": self.inputs.record(), "cache_key": None,
               "generations": {"reduce": self.parent_generation} if hasattr(self, "parent_generation") else {}}
        (self.report_dir / "bisect.json").write_text(json.dumps(rep, indent=1) + "\n")
        if result is None:
            import uuid
            temporary = self.base / f'.bisect-{uuid.uuid4().hex}'
            shutil.copyfile(self.report_dir / 'bisect.json', temporary)
            temporary.replace(self.base / 'bisect.json')
        if result is not None:
            (self.report_dir / "bisect.md").write_text(render_md(rep))
            self.inputs.publish(self.base, ["bisect.json", "bisect.md"], source=self.report_dir)
        return rep


def render_md(r: dict) -> str:
    res = r.get("result") or {}
    L = [f"# Bisect of {r['signature']}", "", f"- Core repo: `{r['core_repo']}` (private clone `{r['clone']}`)",
         f"- Range: good `{r['good']}`, bad `{r['bad']}`", f"- Test: `{r['command']}` with `{r['env']}=<clone>`",
         f"- Max cycles {r.get('max_cycles')} from {r.get('max_cycles_from')}", ""]
    if res.get("first_bad"):
        L += [f"**First bad commit: {res['commit']}**", "", "```", res.get("show", "")[:3000], "```", ""]
    elif res.get("ambiguous"):
        L += [f"Ambiguous (skipped commits): {', '.join(x[:10] for x in res['ambiguous'])}", ""]
    elif res.get("error"):
        L += [f"Error: {res['error']}", ""]
    L += ["| step | commit | result | verdict | cycles | wall s |", "|---|---|---|---|---|---|"]
    for s in r["steps"]:
        L.append(f"| {s['label']} | {s['commit']} | {s['signature']} | {s['verdict']} | {s['cycles']} | {s['wall_s']} |")
    return "\n".join(L) + "\n"
