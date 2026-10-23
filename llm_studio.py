"""Detect local LLM studios on Windows (and POSIX) without machine-specific paths.

Looks at PATH, standard install folders, running processes, and HTTP APIs.
Never requires a hardcoded drive like D:\\ or a specific Windows username.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HTTP_TIMEOUT = 1.4

# id, display name, native API, default ports, process names, PATH names
STUDIOS = (
    {
        "id": "ollama",
        "name": "Ollama",
        "api": "ollama",
        "ports": (11434, 11435, 11436),
        "process": ("ollama.exe", "ollama app.exe", "ollama"),
        "which": ("ollama",),
        "exe": (
            ("LOCALAPPDATA", r"Programs\Ollama\ollama.exe"),
            ("ProgramFiles", r"Ollama\ollama.exe"),
            ("ProgramFiles", r"Ollama\ollama app.exe"),
        ),
    },
    {
        "id": "lmstudio",
        "name": "LM Studio",
        "api": "openai",
        "ports": (1234,),
        "process": ("LM Studio.exe", "lms.exe", "lms"),
        "which": ("lms",),
        "exe": (
            ("LOCALAPPDATA", r"Programs\LM Studio\LM Studio.exe"),
            ("LOCALAPPDATA", r"LM-Studio\LM Studio.exe"),
        ),
        "dirs": (("USERPROFILE", ".lmstudio"),),
    },
    {
        "id": "llamacpp",
        "name": "llama.cpp",
        "api": "openai",
        "ports": (8080, 8081),
        "process": ("llama-server.exe", "llama-server", "llama-cli.exe"),
        "which": ("llama-server", "llama-cli"),
        "exe": (),
    },
    {
        "id": "koboldcpp",
        "name": "KoboldCPP",
        "api": "openai",
        "ports": (5001, 5000),
        "process": ("koboldcpp.exe", "koboldcpp"),
        "which": ("koboldcpp",),
        "exe": (),
    },
    {
        "id": "jan",
        "name": "Jan",
        "api": "openai",
        "ports": (1337,),
        "process": ("Jan.exe", "jan.exe", "jan"),
        "which": ("jan",),
        "exe": (
            ("LOCALAPPDATA", r"Programs\jan\Jan.exe"),
            ("LOCALAPPDATA", r"jan\Jan.exe"),
        ),
    },
    {
        "id": "gpt4all",
        "name": "GPT4All",
        "api": "openai",
        "ports": (4891,),
        "process": ("gpt4all.exe", "gpt4all-chat.exe", "gpt4all"),
        "which": ("gpt4all",),
        "exe": (
            ("LOCALAPPDATA", r"Programs\GPT4All\gpt4all.exe"),
            ("ProgramFiles", r"GPT4All\gpt4all.exe"),
        ),
    },
)


def _env_path(var: str, rel: str) -> Path | None:
    root = os.environ.get(var)
    if not root:
        return None
    path = Path(root) / rel
    return path


def _http_json(url: str, timeout: float = HTTP_TIMEOUT):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status < 200 or status >= 300:
                return None
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    except Exception:
        return None


def _parse_openai_models(data) -> list[dict]:
    out = []
    if not isinstance(data, dict):
        return out
    items = data.get("data")
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("id") or item.get("name") or "").strip()
            if name:
                out.append({"name": name, "size": int(item.get("size") or 0)})
        elif isinstance(item, str) and item.strip():
            out.append({"name": item.strip(), "size": 0})
    return out


def _parse_ollama_models(data) -> list[dict]:
    out = []
    if not isinstance(data, dict):
        return out
    items = data.get("models")
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                out.append({"name": name, "size": int(item.get("size") or 0)})
        elif isinstance(item, str) and item.strip():
            out.append({"name": item.strip(), "size": 0})
    return out


def probe_openai(host: str, port: int) -> list[dict] | None:
    data = _http_json(f"http://{host}:{int(port)}/v1/models")
    if data is None:
        return None
    return _parse_openai_models(data)


def probe_ollama(host: str, port: int) -> list[dict] | None:
    data = _http_json(f"http://{host}:{int(port)}/api/tags")
    if data is None:
        return None
    return _parse_ollama_models(data)


def probe_any(host: str, port: int) -> tuple[str | None, list[dict] | None]:
    """Return (api, models). api is 'ollama' or 'openai'."""
    models = probe_ollama(host, port)
    if models is not None:
        return "ollama", models
    models = probe_openai(host, port)
    if models is not None:
        return "openai", models
    health = _http_json(f"http://{host}:{int(port)}/health")
    if health is not None:
        return "openai", []
    return None, None


def format_model_label(item: dict) -> str:
    name = str(item.get("name") or "")
    try:
        size = int(item.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if size >= 1024**3:
        return f"{name}  ({size / (1024 ** 3):.1f} GB)"
    if size >= 1024**2:
        return f"{name}  ({size / (1024 ** 2):.0f} MB)"
    return name


def _running_process_names() -> set[str]:
    names = set()
    if sys.platform == "win32":
        try:
            raw = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except Exception:
            return names
        for line in raw.splitlines():
            parts = [p.strip().strip('"') for p in line.split(",")]
            if parts:
                names.add(parts[0].lower())
        return names
    try:
        raw = subprocess.check_output(
            ["ps", "-A", "-o", "comm="],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        for line in raw.splitlines():
            base = Path(line.strip()).name.lower()
            if base:
                names.add(base)
    except Exception:
        pass
    return names


def _listening_ports() -> dict[int, str]:
    """port -> process name (best effort)."""
    found: dict[int, str] = {}
    if sys.platform != "win32":
        return found
    try:
        raw = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except Exception:
        return found
    pid_to_name: dict[str, str] = {}
    for line in raw.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[1]
        pid = parts[-1]
        if local.startswith("[::]"):
            continue
        if ":" not in local:
            continue
        try:
            port = int(local.rsplit(":", 1)[-1])
        except ValueError:
            continue
        if pid not in pid_to_name:
            pid_to_name[pid] = _pid_name(pid)
        found[port] = pid_to_name[pid]
    return found


def _pid_name(pid: str) -> str:
    try:
        raw = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=4,
        )
        parts = [p.strip().strip('"') for p in raw.split(",")]
        return parts[0] if parts else ""
    except Exception:
        return ""


def _exe_exists(spec: tuple[str, str]) -> bool:
    path = _env_path(spec[0], spec[1])
    return bool(path and path.is_file())


def _dir_exists(spec: tuple[str, str]) -> bool:
    path = _env_path(spec[0], spec[1])
    return bool(path and path.exists())


def _studio_installed(spec: dict, proc_names: set[str]) -> bool:
    for name in spec.get("which") or ():
        if shutil.which(name):
            return True
    for exe in spec.get("exe") or ():
        if _exe_exists(exe):
            return True
    for folder in spec.get("dirs") or ():
        if _dir_exists(folder):
            return True
    for proc in spec.get("process") or ():
        if proc.lower() in proc_names:
            return True
    return False


def _match_studio_by_process(proc_name: str) -> dict | None:
    needle = (proc_name or "").lower()
    if not needle:
        return None
    for spec in STUDIOS:
        for proc in spec["process"]:
            if needle == proc.lower() or needle.startswith(proc.lower()):
                return spec
    if "llama" in needle and "server" in needle:
        return next(s for s in STUDIOS if s["id"] == "llamacpp")
    if "lm studio" in needle or needle == "lms.exe":
        return next(s for s in STUDIOS if s["id"] == "lmstudio")
    return None


def discover(host: str = "127.0.0.1") -> list[dict]:
    """Return unique studios that are installed and/or serving an API."""
    host = (host or "127.0.0.1").strip() or "127.0.0.1"
    proc_names = _running_process_names()
    listening = _listening_ports()
    found: dict[str, dict] = {}

    def remember(item: dict):
        key = item["id"]
        old = found.get(key)
        if old is None:
            found[key] = item
            return
        if item.get("running") and not old.get("running"):
            found[key] = item
            return
        if item.get("models") and not old.get("models"):
            old["models"] = item["models"]
        old["installed"] = old.get("installed") or item.get("installed")
        old["running"] = old.get("running") or item.get("running")
        if item.get("port") and not old.get("running"):
            old["port"] = item["port"]
            old["host"] = item.get("host") or old.get("host")

    for spec in STUDIOS:
        installed = _studio_installed(spec, proc_names)
        running = False
        models = []
        api = spec["api"]
        port_used = spec["ports"][0]
        for port in spec["ports"]:
            if listening and port not in listening:
                continue
            kind, probed = probe_any(host, port)
            if kind is None:
                continue
            running = True
            api = kind
            port_used = port
            models = probed or []
            break
        if installed or running:
            remember(
                {
                    "id": spec["id"],
                    "name": spec["name"],
                    "api": api,
                    "host": host,
                    "port": int(port_used),
                    "installed": installed,
                    "running": running,
                    "models": models,
                }
            )

    known_ports = {p for spec in STUDIOS for p in spec["ports"]}
    extra_hints = ("llama", "ollama", "lm studio", "lms", "kobold", "jan", "gpt4all", "localai", "textgen", "vllm")
    for port, proc in listening.items():
        if port in known_ports:
            continue
        spec = _match_studio_by_process(proc)
        needle = (proc or "").lower()
        if spec is None and not any(k in needle for k in extra_hints):
            continue
        kind, probed = probe_any(host, port)
        if kind is None:
            continue
        if spec is None:
            sid = f"openai-{port}"
            remember(
                {
                    "id": sid,
                    "name": f"OpenAI-compatible ({proc or 'unknown'} :{port})",
                    "api": kind,
                    "host": host,
                    "port": int(port),
                    "installed": True,
                    "running": True,
                    "models": probed or [],
                }
            )
        else:
            remember(
                {
                    "id": spec["id"],
                    "name": spec["name"],
                    "api": kind,
                    "host": host,
                    "port": int(port),
                    "installed": True,
                    "running": True,
                    "models": probed or [],
                }
            )

    order = [s["id"] for s in STUDIOS]
    items = list(found.values())
    items.sort(
        key=lambda x: (
            0 if x.get("running") else 1,
            order.index(x["id"]) if x["id"] in order else 99,
            x["name"].lower(),
        )
    )
    return items


def status_line(item: dict, lang: str = "en") -> str:
    bits = []
    if item.get("running"):
        bits.append("running" if lang == "en" else "запущена")
        bits.append(f"{item.get('host')}:{item.get('port')}")
        n = len(item.get("models") or [])
        if lang == "en":
            bits.append(f"{n} model" + ("" if n == 1 else "s"))
        else:
            bits.append(f"{n} модел" + ("ь" if n == 1 else "и"))
    elif item.get("installed"):
        bits.append("installed, server off" if lang == "en" else "установлена, сервер выключен")
    return f"{item['name']}  —  " + ", ".join(bits)


def try_start(item: dict) -> bool:
    """Best-effort start for a known CLI. Returns True if the API answers after."""
    sid = item.get("id")
    host = item.get("host") or "127.0.0.1"
    port = int(item.get("port") or 0)
    if sid == "ollama":
        exe = shutil.which("ollama")
        if not exe:
            local = _env_path("LOCALAPPDATA", r"Programs\Ollama\ollama.exe")
            exe = str(local) if local and local.is_file() else None
        if not exe:
            return False
        try:
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
                if sys.platform == "win32"
                else 0,
            )
        except Exception:
            return False
        for _ in range(8):
            import time

            time.sleep(0.6)
            kind, _models = probe_any(host, port or 11434)
            if kind:
                return True
        return False
    if sid == "lmstudio":
        exe = shutil.which("lms")
        if not exe:
            return False
        try:
            subprocess.Popen(
                [exe, "server", "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return False
        import time

        time.sleep(2.0)
        kind, _models = probe_any(host, port or 1234)
        return kind is not None
    return False
