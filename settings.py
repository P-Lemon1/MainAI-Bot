"""Load and save MainAI-Bot runtime settings (wizard -> config.json -> bots)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"

VERSIONS = {
    "1.12": {
        "folder": "1_12",
        "protocol": "1.12",
        "brain": "simple",
        "note_en": "Vanilla 1.12.0 protocol (not 1.12.2). Simple companion.",
        "note_ru": "Протокол ванили 1.12.0 (не 1.12.2). Простой компаньон.",
    },
    "1.16.5": {
        "folder": "1_16",
        "protocol": "1.16.5",
        "brain": "survival",
        "note_en": "Survival companion: collect, craft, PvP, auto-eat.",
        "note_ru": "Выживание: добыча, крафт, PvP, авто-еда.",
    },
    "1.20.1": {
        "folder": "1_20_1",
        "protocol": "1.20.1",
        "brain": "simple",
        "note_en": "Simple companion (follow, mine trees, explore, fight).",
        "note_ru": "Простой компаньон (следовать, рубить, исследовать, драться).",
    },
    "1.21.4": {
        "folder": "1_21_4",
        "protocol": "1.21.4",
        "brain": "simple",
        "note_en": "Simple companion (follow, mine trees, explore, fight).",
        "note_ru": "Простой компаньон (следовать, рубить, исследовать, драться).",
    },
    "1.21.6": {
        "folder": "1_21_6",
        "protocol": "1.21.6",
        "brain": "simple",
        "note_en": "Simple companion (follow, mine trees, explore, fight).",
        "note_ru": "Простой компаньон (следовать, рубить, исследовать, драться).",
    },
}

BOT_KINDS = ("companion", "chat")

DEFAULTS = {
    "language": "ru",
    "mc_version": "1.21.6",
    "bot_kind": "companion",
    "mc_host": "localhost",
    "mc_port": 25565,
    "bot_username": "MainAI",
    "ollama_host": "127.0.0.1",
    "ollama_port": 11434,
    "ollama_model": "qwen2.5-coder:14b",
}


def ollama_url(cfg: dict) -> str:
    host = str(cfg.get("ollama_host") or "127.0.0.1").strip()
    port = int(cfg.get("ollama_port") or 11434)
    return f"http://{host}:{port}/api/chat"


def script_path(cfg: dict) -> Path:
    info = VERSIONS[cfg["mc_version"]]
    name = "ScriptAI.py" if cfg.get("bot_kind") == "companion" else "ScriptAI_chat.py"
    return ROOT / "versions" / info["folder"] / name


def load() -> dict:
    data = dict(DEFAULTS)
    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            data.update(saved)
    return normalize(data)


def require_config() -> dict:
    os.chdir(ROOT)
    if not CONFIG_PATH.is_file():
        print("No config.json found. Run:  python wizard.py")
        print("Нет config.json. Запусти:  python wizard.py")
        sys.exit(1)
    return load()


def normalize(data: dict) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(data or {})

    version = str(cfg.get("mc_version") or "").strip()
    aliases = {"1.16": "1.16.5", "1_16": "1.16.5", "1_12": "1.12"}
    version = aliases.get(version, version)
    if version not in VERSIONS:
        version = DEFAULTS["mc_version"]
    cfg["mc_version"] = version
    cfg["mc_protocol"] = VERSIONS[version]["protocol"]

    kind = str(cfg.get("bot_kind") or "companion").strip().lower()
    cfg["bot_kind"] = kind if kind in BOT_KINDS else "companion"

    cfg["mc_host"] = str(cfg.get("mc_host") or "localhost").strip() or "localhost"
    cfg["mc_port"] = _port(cfg.get("mc_port"), 25565)
    cfg["bot_username"] = str(cfg.get("bot_username") or "MainAI").strip() or "MainAI"

    cfg["ollama_host"] = str(cfg.get("ollama_host") or "127.0.0.1").strip() or "127.0.0.1"
    cfg["ollama_port"] = _port(cfg.get("ollama_port"), 11434)
    cfg["ollama_model"] = (
        str(cfg.get("ollama_model") or "qwen2.5-coder:14b").strip()
        or "qwen2.5-coder:14b"
    )

    lang = str(cfg.get("language") or "ru").strip().lower()
    cfg["language"] = "en" if lang.startswith("en") else "ru"
    return cfg


def save(cfg: dict) -> Path:
    payload = normalize(cfg)
    with CONFIG_PATH.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return CONFIG_PATH


def _port(value, default: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    if 1 <= port <= 65535:
        return port
    return default
