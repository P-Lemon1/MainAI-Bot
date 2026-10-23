#!/usr/bin/env python3
"""Interactive setup wizard: Minecraft version, ports, and local LLM studio."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import llm_studio
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
        "scan": "Looking for local AI studios (Ollama, LM Studio, llama.cpp, …)",
        "none": "No local AI studio found (not installed and no API on this PC).",
        "found": "Found AI studios",
        "pick_studio": "Choose a studio",
        "only_one": "Using the only studio found.",
        "other": "Other — type host, port and API by hand",
        "not_running": "{name} is installed, but its server is not running.",
        "start_hint": "Start the app (or its local server), then pick Retry.",
        "try_start": "Try to start it from the command line",
        "retry": "Scan again",
        "manual": "Enter host / port by hand",
        "pick_other": "Choose another studio",
        "llm_host": "LLM host",
        "llm_port": "LLM port",
        "llm_api": "API type",
        "api_ollama": "Ollama (/api/chat)",
        "api_openai": "OpenAI-compatible (/v1/chat/completions) — LM Studio, llama.cpp, Jan, …",
        "models": "Models in this studio",
        "no_models": "The studio answers, but the model list is empty. Load a model in that app, then retry.",
        "type_model": "Type a model name",
        "model": "Model name",
        "saved": "Saved",
        "need_python": "Need Python 3.10+",
        "need_node": "Need Node.js 18+ (mineflayer)",
        "need_llm": "Need a local LLM studio (Ollama, LM Studio, llama.cpp, …) with at least one model",
        "need_server": "Need a Minecraft server of the same version, online-mode=false for a nick login",
        "install": "Install Python and Node.js dependencies now? [Y/n]: ",
        "run_now": "Start the bot now? [Y/n]: ",
        "next": "Later you can change settings with  python wizard.py  and start with  python run.py",
        "bad_port": "Port must be a number from 1 to 65535.",
        "bad_host": "That looks like a port. Host is an address, for example 127.0.0.1 or localhost.",
        "pick": "Choose a number",
        "invalid": "Invalid choice.",
        "pip_ok": "Python packages installed.",
        "npm_ok": "Node.js packages installed.",
        "install_fail": "Install failed. Run the command yourself:",
        "missing_node": "Node.js / npm not found. Install Node.js 18+, then run:  npm install",
        "summary": "Summary",
        "started_ok": "Server started.",
        "started_fail": "Could not start it automatically. Open the app yourself.",
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
        "scan": "Ищу локальные ИИ-студии (Ollama, LM Studio, llama.cpp, …)",
        "none": "Локальных ИИ-студий не найдено (нет установки и нет API на этом ПК).",
        "found": "Найденные ИИ-студии",
        "pick_studio": "Выбери студию",
        "only_one": "Найдена одна студия — беру её.",
        "other": "Другое — ввести хост, порт и API вручную",
        "not_running": "{name} установлена, но сервер не запущен.",
        "start_hint": "Запусти приложение (или его локальный сервер), затем выбери «Проверить снова».",
        "try_start": "Попробовать запустить из командной строки",
        "retry": "Проверить снова",
        "manual": "Ввести хост / порт вручную",
        "pick_other": "Выбрать другую студию",
        "llm_host": "Хост ИИ",
        "llm_port": "Порт ИИ",
        "llm_api": "Тип API",
        "api_ollama": "Ollama (/api/chat)",
        "api_openai": "Совместимый с OpenAI (/v1/chat/completions) — LM Studio, llama.cpp, Jan, …",
        "models": "Модели в этой студии",
        "no_models": "Студия отвечает, но список моделей пуст. Загрузи модель в приложении и проверь снова.",
        "type_model": "Ввести имя модели",
        "model": "Имя модели",
        "saved": "Сохранено",
        "need_python": "Нужен Python 3.10+",
        "need_node": "Нужен Node.js 18+ (mineflayer)",
        "need_llm": "Нужна локальная ИИ-студия (Ollama, LM Studio, llama.cpp, …) хотя бы с одной моделью",
        "need_server": "Нужен Minecraft-сервер той же версии, online-mode=false для входа по нику",
        "install": "Поставить Python- и Node.js-зависимости сейчас? [Y/n]: ",
        "run_now": "Запустить бота сейчас? [Y/n]: ",
        "next": "Потом настройки:  python wizard.py   запуск:  python run.py",
        "bad_port": "Порт — число от 1 до 65535.",
        "bad_host": "Это похоже на порт. Хост — адрес, например 127.0.0.1 или localhost.",
        "pick": "Введи номер",
        "invalid": "Неверный выбор.",
        "pip_ok": "Python-пакеты установлены.",
        "npm_ok": "Node.js-пакеты установлены.",
        "install_fail": "Установка не удалась. Выполни команду сам:",
        "missing_node": "Node.js / npm не найдены. Поставь Node.js 18+, затем:  npm install",
        "summary": "Итог",
        "started_ok": "Сервер запущен.",
        "started_fail": "Автозапуск не удался. Открой приложение сам.",
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


def ask_host(prompt: str, default: str, t: dict) -> str:
    fallback = default or "127.0.0.1"
    while True:
        raw = ask(prompt, fallback)
        host = (raw or fallback).strip()
        if host.isdigit():
            print(t["bad_host"])
            fallback = "127.0.0.1"
            continue
        return host or fallback


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


def print_needs(t: dict) -> None:
    print()
    print("Requirements / Что нужно")
    print(f"  - {t['need_python']}")
    print(f"  - {t['need_node']}")
    print(f"  - {t['need_llm']}")
    print(f"  - {t['need_server']}")


def pick_model(models, previous: str, t: dict) -> str:
    previous = (previous or "").strip()
    fallback = previous or ""
    if not models:
        print()
        print(t["no_models"])
        return ask(t["model"], fallback)

    options = [(item["name"], llm_studio.format_model_label(item)) for item in models]
    names = [key for key, _label in options]
    options.append(("__type__", t["type_model"]))
    print()
    print(t["models"])
    default_idx = 1
    if previous in names:
        default_idx = names.index(previous) + 1
    for i, (_key, label) in enumerate(options, 1):
        mark = " *" if i == default_idx and _key != "__type__" else ""
        print(f"  {i}) {label}{mark}")
    while True:
        raw = input(f"{t['pick']} [{default_idx}]: ").strip()
        if not raw:
            chosen = options[default_idx - 1][0]
        else:
            try:
                idx = int(raw)
            except ValueError:
                print(t["invalid"])
                continue
            if not (1 <= idx <= len(options)):
                print(t["invalid"])
                continue
            chosen = options[idx - 1][0]
        if chosen == "__type__":
            return ask(t["model"], fallback)
        return chosen


def manual_studio(t: dict, prev: dict) -> dict:
    host = ask_host(t["llm_host"], str(prev.get("llm_host") or "127.0.0.1"), t)
    port = ask_port(t["llm_port"], int(prev.get("llm_port") or 11434), t)
    api = ask_choice(
        t["llm_api"],
        [("ollama", t["api_ollama"]), ("openai", t["api_openai"])],
        t,
    )
    kind, models = llm_studio.probe_any(host, port)
    if kind:
        api = kind
    return {
        "id": "manual",
        "name": "Manual",
        "api": api,
        "host": host,
        "port": port,
        "installed": True,
        "running": kind is not None,
        "models": models or [],
    }


def ensure_running(item: dict, t: dict) -> dict:
    if item.get("running"):
        return item
    print()
    print(t["not_running"].format(name=item.get("name") or item.get("id")))
    print(t["start_hint"])
    while not item.get("running"):
        action = ask_choice(
            t["pick_studio"],
            [
                ("retry", t["retry"]),
                ("start", t["try_start"]),
                ("manual", t["manual"]),
                ("other", t["pick_other"]),
            ],
            t,
        )
        if action == "other":
            return {"id": "__other__"}
        if action == "manual":
            return {"id": "__manual__"}
        if action == "start":
            ok = llm_studio.try_start(item)
            print(t["started_ok"] if ok else t["started_fail"])
        found = {x["id"]: x for x in llm_studio.discover(item.get("host") or "127.0.0.1")}
        refreshed = found.get(item["id"])
        if refreshed:
            item = refreshed
        else:
            kind, models = llm_studio.probe_any(item.get("host") or "127.0.0.1", int(item.get("port") or 0))
            if kind:
                item = dict(item)
                item["running"] = True
                item["api"] = kind
                item["models"] = models or []
    return item


def pick_studio(t: dict, lang: str, prev: dict) -> dict:
    host = str(prev.get("llm_host") or "127.0.0.1")
    while True:
        print()
        print(t["scan"])
        found = llm_studio.discover(host)
        if not found:
            print(t["none"])
            action = ask_choice(
                t["pick_studio"],
                [("retry", t["retry"]), ("manual", t["manual"])],
                t,
            )
            if action == "retry":
                continue
            return manual_studio(t, prev)

        options = [(item["id"], llm_studio.status_line(item, lang)) for item in found]
        options.append(("__manual__", t["other"]))
        if len(found) == 1:
            print(t["only_one"])
            print("  " + llm_studio.status_line(found[0], lang))
            chosen_id = found[0]["id"]
        else:
            chosen_id = ask_choice(t["found"], options, t)
        if chosen_id == "__manual__":
            return manual_studio(t, prev)
        item = next(x for x in found if x["id"] == chosen_id)
        item = ensure_running(item, t)
        if item.get("id") == "__other__":
            continue
        if item.get("id") == "__manual__":
            return manual_studio(t, prev)
        return item


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


def main() -> int:
    print()
    print("=" * 56)
    print(f"  {settings.PROJECT_NAME}  /  setup wizard  /  мастер настройки")
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

    default_nick = settings.DEFAULT_NICK if kind == "companion" else settings.DEFAULT_NICK + "Chat"
    if prev.get("bot_username") in (settings.DEFAULT_NICK, settings.DEFAULT_NICK + "Chat", "MineAI", "MineAIChat"):
        nick_default = default_nick
    else:
        nick_default = prev.get("bot_username") or default_nick

    mc_host = ask_host(t["mc_host"], str(prev.get("mc_host") or "localhost"), t)
    mc_port = ask_port(t["mc_port"], int(prev.get("mc_port") or 25565), t)
    bot_username = ask(t["username"], nick_default)

    studio = pick_studio(t, lang, prev)
    model = pick_model(studio.get("models") or [], str(prev.get("llm_model") or ""), t)

    cfg = settings.normalize(
        {
            "language": lang,
            "mc_version": mc_version,
            "bot_kind": kind,
            "mc_host": mc_host,
            "mc_port": mc_port,
            "bot_username": bot_username,
            "llm_studio": studio.get("id") or "manual",
            "llm_api": studio.get("api") or "openai",
            "llm_host": studio.get("host") or "127.0.0.1",
            "llm_port": studio.get("port") or 11434,
            "llm_model": model,
        }
    )
    path = settings.save(cfg)

    print()
    print(t["summary"])
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"{t['saved']}: {path}")

    if ask_yes(t["install"], True):
        install_deps(t)

    print()
    print(t["next"])
    if ask_yes(t["run_now"], False):
        from run import start_bot

        return start_bot(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
