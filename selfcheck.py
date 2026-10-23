#!/usr/bin/env python3
"""Compile, unit-test, and scan this tree for machine-specific leftovers."""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORBIDDEN = (
    r"D:\programm",
    r"C:\Users\PC",
    "CMeTaHa",
    "perredex",
    "Pampers",
    "num_gpu",
)


def compile_all() -> list[str]:
    errors = []
    for path in ROOT.rglob("*.py"):
        if "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(str(exc))
    return errors


def hygiene() -> list[str]:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".md", ".json", ".txt", ".bat"}:
            continue
        if path.name == "config.json":
            continue
        if "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name in {"selfcheck.py", "test_llm.py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in FORBIDDEN:
            if needle in text:
                hits.append(f"{path.relative_to(ROOT)}: {needle}")
    return hits


def main() -> int:
    print("compile…")
    errors = compile_all()
    if errors:
        print("COMPILE FAIL")
        print("\n".join(errors))
        return 1
    print("compile ok")

    print("unittest…")
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_llm", "-v"],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        return r.returncode

    print("hygiene…")
    hits = hygiene()
    if hits:
        print("PERSONAL DATA IN SOURCE")
        print("\n".join(hits))
        return 1
    print("hygiene ok")

    print("discover studios…")
    sys.path.insert(0, str(ROOT))
    import llm_studio

    found = llm_studio.discover("127.0.0.1")
    if not found:
        print("no studios visible right now (ok on a clean PC if none are installed)")
    for item in found:
        print(" -", llm_studio.status_line(item, "en"))

    print("selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
