#!/usr/bin/env python3
"""Start the MineAI bot using config.json from the wizard."""

from __future__ import annotations

import subprocess
import sys

import settings

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass


def start_bot(cfg: dict | None = None) -> int:
    cfg = settings.normalize(cfg or settings.require_config())
    script = settings.script_path(cfg)
    if not script.is_file():
        print(f"Missing script: {script}")
        return 1

    print(
        f"Starting {cfg['bot_kind']} bot  MC {cfg['mc_version']}  "
        f"{cfg['mc_host']}:{cfg['mc_port']}  as {cfg['bot_username']}"
    )
    print(
        f"LLM {cfg.get('llm_studio')} {cfg['llm_host']}:{cfg['llm_port']}  "
        f"model {cfg['llm_model']}"
    )
    print(f"Script: {script}")
    result = subprocess.run([sys.executable, str(script)], cwd=str(settings.ROOT))
    return result.returncode


def main() -> int:
    return start_bot()


if __name__ == "__main__":
    raise SystemExit(main())
