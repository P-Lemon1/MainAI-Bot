"""Backward-compatible aliases. New code should use llm_studio / llm_client."""

from __future__ import annotations

from llm_studio import (
    format_model_label,
    probe_ollama as fetch_tags,
    probe_any,
)

DEFAULT_PORT = 11434
PROBE_PORTS = (11434, 11435, 11436)


def model_names(models):
    return [m["name"] for m in models or [] if m.get("name")]


def probe_ports(host: str, ports: list[int]):
    seen = []
    for port in ports:
        try:
            port = int(port)
        except (TypeError, ValueError):
            continue
        if port < 1 or port > 65535 or port in seen:
            continue
        seen.append(port)
        models = fetch_tags(host, port)
        if models is not None:
            return port, models
    return None, None
