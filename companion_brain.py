"""Autonomous LLM brain for Mineflayer companions.

The network keeps deciding what to do from world state, not only from chat.
Player chat is a high-priority order. Reflex combat stays in each ScriptAI.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import traceback

import llm_client
import settings

LLM_CFG = {}
CHAT_LANGUAGE = "ru"
THINK_EVERY_SEC = 14
SPEAK_AUTONOMOUS_EVERY_SEC = 50
JSON_FALLBACK_REPLY = "Не понял тебя, повтори короче."
JSON_FALLBACK_REPLY_EN = "I didn't catch that, say it shorter."


def configure(cfg):
    """Point the brain at the LLM studio from config.json."""
    global LLM_CFG, CHAT_LANGUAGE
    LLM_CFG = settings.normalize(cfg or {})
    lang = str(LLM_CFG.get("language") or "ru").strip().lower()
    CHAT_LANGUAGE = "en" if lang.startswith("en") else "ru"
    print(
        f"LLM {LLM_CFG.get('llm_studio')} {LLM_CFG.get('llm_api')} "
        f"{LLM_CFG.get('llm_host')}:{LLM_CFG.get('llm_port')} "
        f"model={LLM_CFG.get('llm_model')!r}  chat_lang={CHAT_LANGUAGE}"
    )


def fallback_reply():
    if CHAT_LANGUAGE == "en":
        return JSON_FALLBACK_REPLY_EN
    return JSON_FALLBACK_REPLY


def reply_language_rule():
    if CHAT_LANGUAGE == "en":
        return (
            "reply is always a short English sentence for in-game chat. "
            "For PLAYER CHAT, reply MUST be non-empty."
        )
    return (
        "reply is always a short Russian sentence for in-game chat. "
        "Для PLAYER CHAT поле reply обязательно непустое."
    )


SURVIVAL_ACTIONS = (
    "collect",
    "pvp_attack",
    "follow",
    "stop",
    "craft",
    "explore",
    "none",
)

SIMPLE_ACTIONS = (
    "follow",
    "stop",
    "mine_tree",
    "look",
    "jump",
    "drop_item",
    "attack",
    "step_back",
    "step_forward",
    "explore",
    "none",
)

SURVIVAL_PROMPT = """You are an autonomous Minecraft survival companion (Mineflayer).
You MUST answer with STRICT JSON only. No markdown, no code fences, no extra text.
JSON:
{
  "reply": "<short in-game chat sentence, or empty string if autonomous>",
  "action": "collect" | "pvp_attack" | "follow" | "stop" | "craft" | "explore" | "none",
  "target": "<minecraft id or player name>",
  "count": <positive integer>
}

English minecraft ids only in target (oak_log, iron_ore, zombie, stick, wooden_pickaxe).
REPLY_LANGUAGE_RULE

How you think:
- You run even when nobody is chatting. Then source is AUTONOMOUS.
- AUTONOMOUS: pick the next useful survival step from world state. If already doing the right thing, action=none and reply="".
- PLAYER CHAT is an order: obey it. It becomes the standing order until they say stop / стой / хватит.
- Do not spam chat. AUTONOMOUS reply should usually be "".
- Speak (non-empty reply) only for player chat, or when something important happens (fight, low health, found ore).

Priorities when autonomous:
1. Hostile very close or health < 10 -> pvp_attack that mob (or stop and follow player if player is safer).
2. Standing order from the player -> keep doing it.
3. Night + player nearby -> follow the player.
4. No wood / no crafting_table / no wooden tools -> collect oak_log then craft oak_planks, crafting_table, wooden_pickaxe.
5. Useful nearby ores -> collect them (count 4-8).
6. Otherwise explore a bit, then follow the nearest player if any.
7. If following and everything is fine -> none.
"""

SIMPLE_PROMPT = """You are an autonomous Minecraft companion (Mineflayer).
You MUST answer with STRICT JSON only. No markdown, no extra text.
JSON:
{
  "reply": "<short in-game chat sentence, or empty string if autonomous>",
  "action": "follow" | "stop" | "mine_tree" | "look" | "jump" | "drop_item" | "attack" | "step_back" | "step_forward" | "explore" | "none",
  "target": "<optional player or mob name>"
}

REPLY_LANGUAGE_RULE
target uses English minecraft ids when needed.

You think even without chat (AUTONOMOUS). Then usually reply="".
PLAYER CHAT is an order — obey it.

Autonomous priorities:
1. Hostile close or low health -> attack
2. Player standing order
3. Night or player nearby -> follow
4. Need wood -> mine_tree
5. Otherwise explore or follow
6. If already following and safe -> none
"""


def parse_ai_response(raw_text, valid_actions):
    default = {
        "reply": "",
        "action": "none",
        "target": "",
        "count": 1,
    }
    if not raw_text or not str(raw_text).strip():
        return default

    text = str(raw_text).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    data = None
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return default
        else:
            return default

    if not isinstance(data, dict):
        return default

    reply = data.get("reply", "")
    if reply is None:
        reply = ""
    else:
        reply = str(reply).strip()

    action = data.get("action", "none")
    if not isinstance(action, str) or action not in valid_actions:
        action = "none"
    if action == "pvp_attack" and "pvp_attack" not in valid_actions:
        action = "attack" if "attack" in valid_actions else "none"
    if action == "collect" and "collect" not in valid_actions:
        action = "mine_tree" if "mine_tree" in valid_actions else "none"
    if action == "attack" and "attack" not in valid_actions:
        action = "pvp_attack" if "pvp_attack" in valid_actions else "none"
    if action == "mine_tree" and "mine_tree" not in valid_actions:
        action = "collect" if "collect" in valid_actions else "none"

    target = data.get("target", "")
    if target is None:
        target = ""
    else:
        target = str(target).strip()

    try:
        count = int(data.get("count", 1))
    except (TypeError, ValueError):
        count = 1
    if count < 1:
        count = 1
    count = min(count, 64)

    return {"reply": reply, "action": action, "target": target, "count": count}


def call_ollama(system_prompt, user_content, timeout=25):
    return llm_client.complete(
        LLM_CFG,
        system_prompt,
        user_content,
        json_mode=True,
        timeout=timeout,
    )


def _safe_list(js_obj, limit=24):
    out = []
    if js_obj is None:
        return out
    try:
        seq = list(js_obj)
    except Exception:
        try:
            seq = list(js_obj.keys())
        except Exception:
            return out
    for item in seq[:limit]:
        out.append(item)
    return out


def snapshot_world(bot, extra=None):
    """Compact English world state for the model."""
    lines = []
    try:
        health = getattr(bot, "health", "?")
        food = getattr(bot, "food", "?")
        lines.append(f"health={health}/20 food={food}/20")
    except Exception:
        pass

    try:
        tod = int(bot.time.timeOfDay)
        phase = "night" if tod > 12500 or tod < 1000 else "day"
        lines.append(f"timeOfDay={tod} ({phase})")
    except Exception:
        pass

    try:
        pos = bot.entity.position
        lines.append(f"pos={int(pos.x)},{int(pos.y)},{int(pos.z)}")
    except Exception:
        pass

    try:
        dim = getattr(getattr(bot, "game", None), "dimension", None)
        if dim is not None:
            lines.append(f"dimension={dim}")
    except Exception:
        pass

    inv = []
    try:
        items = bot.inventory.items()
        for it in _safe_list(items, 18):
            name = getattr(it, "name", None)
            count = getattr(it, "count", 1)
            if name:
                inv.append(f"{name}x{count}")
    except Exception:
        pass
    lines.append("inventory=" + (", ".join(inv) if inv else "(empty)"))

    hostiles = []
    players = []
    bot_pos = getattr(getattr(bot, "entity", None), "position", None)
    bot_name = normalize_name(getattr(bot, "username", ""))
    try:
        entities = bot.entities
        ids = _safe_list(entities, 40)
        for eid in ids:
            try:
                ent = entities[eid]
            except Exception:
                continue
            if ent is None:
                continue
            kind = str(getattr(ent, "type", "") or "")
            name = str(getattr(ent, "name", "") or "")
            pos = getattr(ent, "position", None)
            dist = None
            if bot_pos is not None and pos is not None:
                try:
                    dist = round(pos.distanceTo(bot_pos), 1)
                except Exception:
                    dist = None
            if kind == "player":
                if normalize_name(name) == bot_name:
                    continue
                if dist is None or dist < 48:
                    players.append(f"{name}@{dist}")
            elif kind in ("mob", "monster", "hostile") and dist is not None and dist < 16:
                hostiles.append(f"{name}@{dist}")
    except Exception:
        pass
    lines.append("players=" + (", ".join(players[:8]) if players else "none"))
    lines.append("hostiles=" + (", ".join(hostiles[:8]) if hostiles else "none"))

    if extra:
        for key, val in extra.items():
            lines.append(f"{key}={val}")
    return "\n".join(lines)


def normalize_name(value):
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def looks_like_stop(message):
    text = str(message or "").lower()
    keys = (
        "стоп",
        "стой",
        "стоять",
        "хватит",
        "отмена",
        "stop",
        "stay",
        "halt",
        "cancel",
    )
    return any(k in text for k in keys)


class CompanionBrain:
    def __init__(
        self,
        bot,
        *,
        mode="survival",
        apply_action,
        speak,
        extra_state=None,
        on_stop=None,
        busy=None,
    ):
        self.bot = bot
        self.mode = mode
        self.apply_action = apply_action
        self.speak = speak
        self.extra_state = extra_state or (lambda: {})
        self.on_stop = on_stop
        self.busy = busy
        self.valid = SURVIVAL_ACTIONS if mode == "survival" else SIMPLE_ACTIONS
        base = SURVIVAL_PROMPT if mode == "survival" else SIMPLE_PROMPT
        self.prompt = base.replace("REPLY_LANGUAGE_RULE", reply_language_rule())
        self.jobs = queue.Queue()
        self.standing_order = None
        self.last_player = None
        self.last_autonomous_speak = 0
        self._thread = None
        self.alive = True

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="companion-brain", daemon=True
        )
        self._thread.start()
        print("Companion brain started (autonomous + chat)")

    def enqueue_chat(self, username, message):
        self.last_player = username
        if looks_like_stop(message):
            self.standing_order = None
            if self.on_stop:
                try:
                    self.on_stop()
                except Exception as e:
                    print(f"on_stop error: {e}")
        else:
            self.standing_order = str(message)[:180]
        self.jobs.put(("chat", username, str(message)))

    def _loop(self):
        last_think = 0
        while self.alive:
            job = None
            try:
                job = self.jobs.get(timeout=1.0)
            except queue.Empty:
                job = None

            try:
                if job is not None:
                    kind, username, message = job
                    self._decide(
                        autonomous=False, username=username, message=message
                    )
                    last_think = time.time()
                    continue

                if time.time() - last_think < THINK_EVERY_SEC:
                    continue
                if self.busy and self.busy():
                    continue
                try:
                    if getattr(self.bot, "entity", None) is None:
                        continue
                except Exception:
                    continue
                self._decide(autonomous=True)
                last_think = time.time()
            except Exception as e:
                print(f"Brain tick error: {e}")
                traceback.print_exc()
            finally:
                if job is not None:
                    try:
                        self.jobs.task_done()
                    except Exception:
                        pass

    def _decide(self, autonomous, username=None, message=None):
        extra = {
            "following": self.extra_state().get("following"),
            "standing_order": self.standing_order or "(none)",
            "last_player": self.last_player or "(none)",
            "source": "AUTONOMOUS" if autonomous else "PLAYER_CHAT",
        }
        world = snapshot_world(self.bot, extra)
        if autonomous:
            user = (
                "[AUTONOMOUS TICK — nobody is chatting]\n"
                f"{world}\n"
                "Choose the next action. If already fine, action=none and reply=\"\"."
            )
        else:
            user = (
                "[PLAYER CHAT — this is an order]\n"
                f"{world}\n"
                f"Player {username} says: {message}\n"
                "You MUST put a short non-empty reply in JSON (answer or confirm the order)."
            )

        raw = call_ollama(self.prompt, user)
        parsed = parse_ai_response(raw, self.valid)
        action = parsed["action"]
        target = parsed["target"]
        count = parsed["count"]
        reply = parsed["reply"]

        print(
            f"Brain [{'auto' if autonomous else 'chat'}]: "
            f"action={action} target={target} count={count} reply={reply!r}"
        )

        speaker = username or self.last_player
        if not autonomous:
            if not reply:
                reply = fallback_reply()
            self.speak(reply)
        else:
            now = time.time()
            important = action in ("pvp_attack", "attack") or (
                extra.get("following") is None and action != "none"
            )
            if (
                reply
                and important
                and now - self.last_autonomous_speak >= SPEAK_AUTONOMOUS_EVERY_SEC
            ):
                self.speak(reply)
                self.last_autonomous_speak = now

        if action == "stop":
            self.standing_order = None

        self.apply_action(action, speaker, target, count)
