"""Listen to Mineflayer chat on 1.8–1.21 without handling the same line twice."""

from __future__ import annotations

import time

from javascript import On

_KEEP_ALIVE = []


def bind(bot, on_message):
    """Call on_message(username, message) for other players' chat."""
    last = {"sig": None, "t": 0.0}

    def ingest(username, message):
        if username is None or message is None:
            return
        username = str(username)
        message = str(message)
        if not message.strip():
            return
        try:
            me = str(bot.username)
        except Exception:
            me = ""
        if username == me:
            return
        now = time.time()
        sig = (username, message)
        if last["sig"] == sig and (now - last["t"]) < 0.6:
            return
        last["sig"] = sig
        last["t"] = now
        on_message(username, message)

    @On(bot, "chat")
    def _chat(this, username, message, *args):
        ingest(username, message)

    @On(bot, "playerChat")
    def _player_chat(this, *args):
        if not args:
            return
        data = args[0]
        username = None
        message = None
        if hasattr(data, "username"):
            username = getattr(data, "username", None)
            message = getattr(data, "plainMessage", None) or getattr(data, "message", None)
        elif len(args) >= 2:
            username, message = args[0], args[1]
        ingest(username, message)

    @On(bot, "whisper")
    def _whisper(this, username, message, *args):
        ingest(username, message)

    _KEEP_ALIVE.extend((_chat, _player_chat, _whisper))
    return ingest
