"""Talk to a local LLM studio (Ollama native or OpenAI-compatible HTTP)."""

from __future__ import annotations

import json
from typing import Any

import requests

import settings


def complete_messages(
    cfg: dict,
    messages: list[dict],
    *,
    json_mode: bool = False,
    timeout: int = 25,
) -> str:
    cfg = settings.normalize(cfg)
    api = str(cfg.get("llm_api") or "ollama")
    model = str(cfg.get("llm_model") or "").strip()
    if not model:
        raise RuntimeError("No LLM model in config.json. Run: python wizard.py")
    if api == "ollama":
        return _ollama_chat(cfg, messages, json_mode=json_mode, timeout=timeout)
    return _openai_chat(cfg, messages, json_mode=json_mode, timeout=timeout)


def complete(
    cfg: dict,
    system_prompt: str,
    user_content: str,
    *,
    json_mode: bool = False,
    timeout: int = 25,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return complete_messages(cfg, messages, json_mode=json_mode, timeout=timeout)


def _ollama_chat(cfg: dict, messages: list[dict], json_mode: bool, timeout: int) -> str:
    url = f"http://{cfg['llm_host']}:{int(cfg['llm_port'])}/api/chat"
    payload: dict[str, Any] = {
        "model": cfg["llm_model"],
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": 1536},
    }
    if json_mode:
        payload["format"] = "json"
    res = requests.post(url, json=payload, timeout=timeout)
    if res.status_code != 200:
        raise RuntimeError(f"Ollama HTTP {res.status_code}: {res.text[:240]}")
    data = res.json()
    return str((data.get("message") or {}).get("content") or "")


def _openai_chat(cfg: dict, messages: list[dict], json_mode: bool, timeout: int) -> str:
    url = f"http://{cfg['llm_host']}:{int(cfg['llm_port'])}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": cfg["llm_model"],
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    res = requests.post(url, json=payload, timeout=timeout)
    if res.status_code in (400, 422) and json_mode:
        payload.pop("response_format", None)
        res = requests.post(url, json=payload, timeout=timeout)
    if res.status_code != 200:
        raise RuntimeError(f"LLM HTTP {res.status_code}: {res.text[:240]}")
    data = res.json()
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                parts.append(str(chunk.get("text") or ""))
            elif isinstance(chunk, str):
                parts.append(chunk)
        return "".join(parts)
    return str(content or "")
