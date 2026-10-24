"""Build a project-owned SpinalDB entry without a workstation entry name."""
from contextlib import nullcontext
from pathlib import Path
import os
import tempfile

from rvw.common.capture import Capture
from rvw.common.lock import held
from rvw.common.proc import run_group
from rvw.common.project import find_project, load_project
from rvw.regress.config import load_config
from .db import QueryError, run_on
from . import ops


def build_database(project=None, config=None, out=None, *, job=None, options=None):
    with tempfile.TemporaryDirectory(prefix="rvw-query-build-") as directory:
        capture = Capture(Path(directory) / "inputs")
        selected = load_project(project, capture=capture)
        if selected is None or not selected.get("query", "build"):
            raise ValueError("select a project with query.build")
        core = load_config(project=find_project(project), capture=capture)
        out = Path(out or selected.get("query", "db") or "design.db").absolute()
        out.parent.mkdir(parents=True, exist_ok=True)
        command = [*selected.get("query", "build"), config or core.default_config, str(out), *(options or [])]
        env = os.environ.copy()
        if core.source_env:
            env[core.source_env] = str(core.source_repo)
        # Build scripts own their toolchain and elaboration capture. Keep project and
        # launcher provenance beside the resulting database information.
        for arg in selected.get("query", "build"):
            if Path(arg).is_file():
                capture.file(arg)
        with held(core.lock, directory=core.lock_dir) if core.lock else nullcontext():
            protected = {selected.path.resolve(), *(Path(arg).resolve() for arg in selected.get("query", "build") if Path(arg).is_file())}
            if out.resolve() in protected:
                raise ValueError("database output aliases a project input")
            # A successful launcher that wrote nothing must not return an old DB.
            out.unlink(missing_ok=True)
            if job:
                job.set_progress("elaborating")
                code = job.run(command, cwd=selected.root, env=env)
            else:
                import sys
                process = run_group(command, cwd=selected.root, env=env, stdout=sys.stderr, stderr=sys.stderr)
                code = process.returncode
        if code:
            raise QueryError(f"project database build failed with exit code {code}")
        result = run_on(out, ops.info)
        result["project_capture"] = capture.record()
        return result
