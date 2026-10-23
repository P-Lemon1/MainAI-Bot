"""Unit tests that do not need a live Minecraft server or GPU."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import llm_studio  # noqa: E402
import settings  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_spawn_greeting_ru_companion(self):
        text = settings.spawn_greeting(
            {"language": "ru", "bot_kind": "companion", "bot_username": "Steve"}
        )
        self.assertEqual(text, "Привет, я Steve, твой компаньон.")

    def test_spawn_greeting_en_chat(self):
        text = settings.spawn_greeting(
            {"language": "en", "bot_kind": "chat", "bot_username": "Alex"}
        )
        self.assertEqual(text, "Hello, I am Alex, your chat bot.")

    def test_migrate_old_ollama_keys(self):
        cfg = settings.normalize(
            {
                "ollama_host": "127.0.0.1",
                "ollama_port": 11434,
                "ollama_model": "llama3.1:8b",
            }
        )
        self.assertEqual(cfg["llm_host"], "127.0.0.1")
        self.assertEqual(cfg["llm_port"], 11434)
        self.assertEqual(cfg["llm_model"], "llama3.1:8b")
        self.assertEqual(cfg["llm_api"], "ollama")

    def test_numeric_host_rejected(self):
        cfg = settings.normalize({"llm_host": "11434", "ollama_host": "11434"})
        self.assertEqual(cfg["llm_host"], "127.0.0.1")

    def test_default_nick_not_personal(self):
        self.assertNotIn("CMeTaHa", settings.DEFAULT_NICK)
        self.assertEqual(settings.normalize({})["mc_port"], 25565)


class StudioDetectTests(unittest.TestCase):
    def test_parse_openai_models(self):
        data = {"data": [{"id": "qwen2.5-7b"}, {"id": "llama-3"}]}
        names = [m["name"] for m in llm_studio._parse_openai_models(data)]
        self.assertEqual(names, ["qwen2.5-7b", "llama-3"])

    def test_parse_ollama_models(self):
        data = {"models": [{"name": "qwen2.5-coder:14b", "size": 10}]}
        items = llm_studio._parse_ollama_models(data)
        self.assertEqual(items[0]["name"], "qwen2.5-coder:14b")

    def test_status_line_running(self):
        line = llm_studio.status_line(
            {
                "name": "Ollama",
                "running": True,
                "host": "127.0.0.1",
                "port": 11434,
                "models": [{}, {}],
            },
            "en",
        )
        self.assertIn("Ollama", line)
        self.assertIn("11434", line)
        self.assertIn("2 model", line)

    def test_no_hardcoded_personal_paths_in_studios(self):
        blob = json.dumps(llm_studio.STUDIOS)
        self.assertNotIn("D:\\\\", blob)
        self.assertNotIn("C:\\\\Users\\\\PC", blob)
        self.assertNotIn("programm\\\\ollama", blob)


class SourceHygieneTests(unittest.TestCase):
    FORBIDDEN = (
        "CMeTaHa",
        "perredex",
        r"D:\programm",
        r"C:\Users\PC",
    )

    def test_repo_python_has_no_personal_data(self):
        skip = {"config.json", "node_modules"}
        hits = []
        for path in ROOT.rglob("*.py"):
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            if path.name in {"selfcheck.py", "test_llm.py"}:
                continue
            text = path.read_text(encoding="utf-8")
            for needle in self.FORBIDDEN:
                if needle in text:
                    hits.append(f"{path.name}: {needle}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
