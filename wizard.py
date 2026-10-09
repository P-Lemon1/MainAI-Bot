#!/usr/bin/env python3
"""Interactive setup wizard for MainAI-Bot (version, ports, and required extras)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import settings

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass


T = {
    "en": {
        "title": "MainAI-Bot setup wizard",
        "have_config": "Found existing config.json. Empty answer keeps the current value.",
        "lang_ok": "Language: English",
        "version": "Minecraft version",
        "kind": "Bot type",
        "kind_1": "Companion — the neural net walks, mines, fights, follows (ScriptAI)",
        "kind_2": "Chat spectator — answers messages that start with '.' (ScriptAI_chat)",
        "mc_host": "Minecraft server host",
        "mc_port": "Minecraft server port",
        "username": "Bot username (offline / cracked nick)",
        "ollama_host": "Ollama host",
        "ollama_port": "Ollama port",
        "ollama_model": "Ollama model (must already be pulled)",
        "saved": "Saved",
        "need_python": "Need Python 3.10+",
        "need_node": "Need Node.js 18+ (mineflayer)",
        "need_ollama": "Need Ollama running with the chosen model",
        "need_server": "Need a Minecraft server of the same version, online-mode=false for a nick login",
        "install": "Install Python and Node.js dependencies now? [Y/n]: ",
        "check_ollama": "Check that Ollama answers on this port? [Y/n]: ",
        "ollama_ok": "Ollama is reachable.",
        "ollama_fail": "Ollama did not answer. Start it, then:  ollama pull {model}",
        "run_now": "Start the bot now? [Y/n]: ",
        "next": "Later you can change settings with  python wizard.py  and start with  python run.py",
        "bad_port": "Port must be a number from 1 to 65535.",
        "pick": "Choose a number",
        "invalid": "Invalid choice.",
        "pip_ok": "Python packages installed.",
        "npm_ok": "Node.js packages installed.",
        "install_fail": "Install failed. Run the command yourself:",
        "missing_node": "Node.js / npm not found. Install Node.js 18+, then run:  npm install",
        "summary": "Summary",
    },
    "ru": {
        "title": "Мастер настройки MainAI-Bot",
        "have_config": "Найден config.json. Пустой ответ оставляет текущее значение.",
        "lang_ok": "Язык: русский",
        "version": "Версия Minecraft",
        "kind": "Тип бота",
        "kind_1": "Компаньон — нейросеть ходит, добывает, дерётся, следует (ScriptAI)",
        "kind_2": "Чат-зритель — отвечает на сообщения с точки '.' (ScriptAI_chat)",
        "mc_host": "Хост Minecraft-сервера",
        "mc_port": "Порт Minecraft-сервера",
        "username": "Ник бота (оффлайн / пиратский ник)",
        "ollama_host": "Хост Ollama",
        "ollama_port": "Порт Ollama",
        "ollama_model": "Модель Ollama (уже должна быть скачана)",
        "saved": "Сохранено",
        "need_python": "Нужен Python 3.10+",
        "need_node": "Нужен Node.js 18+ (mineflayer)",
        "need_ollama": "Нужна запущенная Ollama с выбранной моделью",
        "need_server": "Нужен Minecraft-сервер той же версии, online-mode=false для входа по нику",
        "install": "Поставить Python- и Node.js-зависимости сейчас? [Y/n]: ",
        "check_ollama": "Проверить, отвечает ли Ollama на этом порту? [Y/n]: ",
        "ollama_ok": "Ollama отвечает.",
        "ollama_fail": "Ollama не ответила. Запусти её, затем:  ollama pull {model}",
        "run_now": "Запустить бота сейчас? [Y/n]: ",
        "next": "Потом настройки:  python wizard.py   запуск:  python run.py",
        "bad_port": "Порт — число от 1 до 65535.",
        "pick": "Введи номер",
        "invalid": "Неверный выбор.",
        "pip_ok": "Python-пакеты установлены.",
        "npm_ok": "Node.js-пакеты установлены.",
        "install_fail": "Установка не удалась. Выполни команду сам:",
        "missing_node": "Node.js / npm не найдены. Поставь Node.js 18+, затем:  npm install",
        "summary": "Итог",
    },
}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default != "" else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def ask_yes(prompt: str, default_yes: bool = True) -> bool:
    raw = input(prompt).strip().lower()
    if not raw:
        return default_yes
    return raw in ("y", "yes", "д", "да")


def ask_port(prompt: str, default: int, t: dict) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            port = int(raw)
        except ValueError:
            print(t["bad_port"])
            continue
        if 1 <= port <= 65535:
            return port
        print(t["bad_port"])


def ask_choice(title: str, options: list[tuple[str, str]], t: dict) -> str:
    print()
    print(title)
    for i, (_key, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        raw = input(f"{t['pick']}: ").strip()
        try:
            idx = int(raw)
        except ValueError:
            print(t["invalid"])
            continue
        if 1 <= idx <= len(options):
            return options[idx - 1][0]
        print(t["invalid"])


def pick_language() -> str:
    print()
    print("Language / Язык")
    print("  1) English")
    print("  2) Русский")
    while True:
        raw = input("1/2: ").strip()
        if raw in ("1", "en", "english"):
            return "en"
        if raw in ("2", "ru", "рус", "русский"):
            return "ru"
        print("1 or 2 / 1 или 2")


def check_ollama(cfg: dict) -> bool:
    try:
        import urllib.request

        url = f"http://{cfg['ollama_host']}:{cfg['ollama_port']}/api/tags"
        with urllib.request.urlopen(url, timeout=4) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except Exception:
        return False


def install_deps(t: dict) -> None:
    pip = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(settings.ROOT / "requirements.txt"),
    ]
    print(">", " ".join(pip))
    r1 = subprocess.run(pip, cwd=str(settings.ROOT))
    if r1.returncode == 0:
        print(t["pip_ok"])
    else:
        print(t["install_fail"], " ".join(pip))

    npm = shutil.which("npm")
    if not npm:
        print(t["missing_node"])
        return
    cmd = [npm, "install"]
    print(">", " ".join(cmd))
    r2 = subprocess.run(cmd, cwd=str(settings.ROOT), shell=(sys.platform == "win32"))
    if r2.returncode == 0:
        print(t["npm_ok"])
    else:
        print(t["install_fail"], "npm install")


def print_needs(t: dict) -> None:
    print()
    print("Requirements / Что нужно")
    print(f"  - {t['need_python']}")
    print(f"  - {t['need_node']}")
    print(f"  - {t['need_ollama']}")
    print(f"  - {t['need_server']}")


def main() -> int:
    print()
    print("=" * 56)
    print("  MainAI-Bot  /  setup wizard  /  мастер настройки")
    print("=" * 56)

    existing = settings.CONFIG_PATH.is_file()
    prev = settings.load() if existing else dict(settings.DEFAULTS)

    lang = pick_language()
    t = T[lang]
    print(t["lang_ok"])
    if existing:
        print(t["have_config"])

    print_needs(t)

    version_opts = []
    for key, info in settings.VERSIONS.items():
        note = info["note_en"] if lang == "en" else info["note_ru"]
        version_opts.append((key, f"{key}  —  {note}"))
    mc_version = ask_choice(t["version"], version_opts, t)

    kind = ask_choice(
        t["kind"],
        [("companion", t["kind_1"]), ("chat", t["kind_2"])],
        t,
    )

    default_nick = "MainAI" if kind == "companion" else "MainAIChat"
    if prev.get("bot_username") in ("MainAI", "MainAIChat"):
        nick_default = default_nick
    else:
        nick_default = prev.get("bot_username") or default_nick

    mc_host = ask(t["mc_host"], str(prev.get("mc_host") or "localhost"))
    mc_port = ask_port(t["mc_port"], int(prev.get("mc_port") or 25565), t)
    bot_username = ask(t["username"], nick_default)
    ollama_host = ask(t["ollama_host"], str(prev.get("ollama_host") or "127.0.0.1"))
    ollama_port = ask_port(t["ollama_port"], int(prev.get("ollama_port") or 11434), t)
    ollama_model = ask(
        t["ollama_model"],
        str(prev.get("ollama_model") or "qwen2.5-coder:14b"),
    )

    cfg = settings.normalize(
        {
            "language": lang,
            "mc_version": mc_version,
            "bot_kind": kind,
            "mc_host": mc_host,
            "mc_port": mc_port,
            "bot_username": bot_username,
            "ollama_host": ollama_host,
            "ollama_port": ollama_port,
            "ollama_model": ollama_model,
        }
    )
    path = settings.save(cfg)

    print()
    print(t["summary"])
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"{t['saved']}: {path}")

    if ask_yes(t["install"], True):
        install_deps(t)

    if ask_yes(t["check_ollama"], True):
        if check_ollama(cfg):
            print(t["ollama_ok"])
        else:
            print(t["ollama_fail"].format(model=cfg["ollama_model"]))

    print()
    print(t["next"])
    if ask_yes(t["run_now"], False):
        from run import start_bot

        return start_bot(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
