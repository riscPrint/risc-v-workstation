"""JUnit XML export of C3 results, for CI dashboards that read JUnit."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from .schema import SuiteResults


_INVALID_XML = re.compile(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def _xml_text(value: str) -> str:
    def escape(match):
        code = ord(match[0])
        return f"\\x{code:02x}" if code <= 0xff else f"\\u{code:04x}"
    return _INVALID_XML.sub(escape, value)


def _case_name(t) -> str:
    seed = t.seed if t.seed is not None else None
    return f"{t.id} (seed {seed})" if seed is not None and t.extra.get("multi_seed") else t.id


def to_junit(results: SuiteResults | Iterable[SuiteResults]) -> ET.ElementTree:
    """One <testsuite> per C3 results dir, named `<suite>.<config>`."""
    if isinstance(results, SuiteResults):
        results = [results]
    root = ET.Element("testsuites")
    total = {"tests": 0, "failures": 0, "errors": 0}
    for res in results:
        name = f"{res.suite}.{res.config}"
        ts = ET.SubElement(root, "testsuite", name=name, timestamp=res.created)
        props = ET.SubElement(ts, "properties")
        for k in ("core_rev", "core_dirty", "tools_rev"):
            if k in res.source:
                ET.SubElement(props, "property", name=k, value=str(res.source[k]))
        ET.SubElement(props, "property", name="run_id", value=res.run_id)
        n = fails = errs = 0
        time = 0.0
        for t in res.tests:
            n += 1
            time += t.wall_s or 0.0
            tc = ET.SubElement(ts, "testcase", classname=f"{res.core}.{name}", name=_case_name(t),
                               time=f"{t.wall_s or 0.0:.3f}")
            if t.status == "pass" and t.conclusive:
                continue
            text = "\n".join(x for x in (
                f"status: {t.status}", f"signature: {t.signature}",
                f"seed: {t.seed}" if t.seed is not None else "",
                f"run: {t.run}" if t.run else "",
                f"message: {t.extra.get('message')}" if t.extra.get("message") else "",
                f"inconclusive: {t.extra.get('inconclusive')}" if t.extra.get("inconclusive") else "") if x)
            if t.status == "pass":
                # An inconclusive pass (C1 `inconclusive`) proves nothing: an error, not a pass.
                errs += 1
                why = t.extra.get("inconclusive")
                el = ET.SubElement(tc, "error", type="inconclusive",
                                   message=why if isinstance(why, str) else "inconclusive pass")
            elif t.status == "error":
                errs += 1
                el = ET.SubElement(tc, "error", type=t.status, message=t.signature or t.status)
            else:
                fails += 1
                el = ET.SubElement(tc, "failure", type=t.status, message=t.signature or t.status)
            el.text = text
        ts.set("tests", str(n))
        ts.set("failures", str(fails))
        ts.set("errors", str(errs))
        ts.set("time", f"{time:.3f}")
        total["tests"] += n
        total["failures"] += fails
        total["errors"] += errs
    for k, v in total.items():
        root.set(k, str(v))
    # ElementTree escapes markup but permits characters that XML 1.0 forbids.
    for element in root.iter():
        element.attrib.update({key: _xml_text(value) for key, value in element.attrib.items()})
        if element.text is not None:
            element.text = _xml_text(element.text)
        if element.tail is not None:
            element.tail = _xml_text(element.tail)
    ET.indent(root)
    return ET.ElementTree(root)


def write_junit(results: SuiteResults | Iterable[SuiteResults], path: str | os.PathLike) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    to_junit(results).write(p, encoding="utf-8", xml_declaration=True)
    return p
