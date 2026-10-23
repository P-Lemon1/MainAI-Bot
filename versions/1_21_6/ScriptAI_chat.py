
from javascript import require, On
import re

import queue
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import settings
import chat_inbox
import llm_client

_cfg = settings.require_config()

mineflayer = require('mineflayer')

# Minecraft 1.21.6 protocol
MC_VERSION = '1.21.6'

SYSTEM_PROMPT = (
    'You are a friendly AI companion in Minecraft chat. '
    'Reply with a short, natural sentence in Russian. '
    'Plain text only — no JSON, no markdown, no code fences, no actions.'
)

FALLBACK_REPLY = 'Не понял тебя, повтори короче.'
MAX_HISTORY = 15
WORKER_PAUSE_SEC = 0.8

# Matches -m or {-m} / { -m } as a standalone flag
FLAG_M_RE = re.compile(r'\{\s*-m\s*\}|(?<![\w-])-m(?![\w-])', re.IGNORECASE)

chat_history = []
history_lock = threading.Lock()
request_queue = queue.Queue()

bot = mineflayer.createBot({
    'host': _cfg['mc_host'],
    'port': _cfg['mc_port'],
    'username': _cfg['bot_username'],
    'version': MC_VERSION
})


def parse_dot_message(message):
    """
    Parse a chat line that starts with '.'.
    Returns (text_for_ai, whisper) or (None, False) if there is nothing to send.
    """
    text = message[1:]
    whisper = bool(FLAG_M_RE.search(text))
    text = FLAG_M_RE.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return None, whisper
    return text, whisper


def send_reply(username, reply, whisper):
    text = str(reply).strip() or FALLBACK_REPLY
    if len(text) > 240:
        text = text[:240]
    if whisper:
        bot.chat(f'/msg {username} {text}')
    else:
        bot.chat(text)


def append_history(role, content):
    """Store one turn and keep only the last MAX_HISTORY messages."""
    global chat_history
    with history_lock:
        chat_history.append({'role': role, 'content': content})
        if len(chat_history) > MAX_HISTORY:
            chat_history = chat_history[-MAX_HISTORY:]


def snapshot_history():
    with history_lock:
        return list(chat_history)


def process_ai_request(username, clean_message, whisper):
    """One Ollama call plus chat/whisper reply. Runs only on the worker thread."""
    append_history('user', f'{username}: {clean_message}')

    try:
        raw_reply = llm_client.complete_messages(
            _cfg,
            [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                *snapshot_history(),
            ],
            timeout=20,
        )
    except Exception as e:
        print(f'LLM error: {e}')
        return
    bot_reply = str(raw_reply).strip() if raw_reply else FALLBACK_REPLY
    if not bot_reply:
        bot_reply = FALLBACK_REPLY

    append_history('assistant', bot_reply)

    mode = 'whisper' if whisper else 'chat'
    print(f'AI_Partner [{mode}]: {bot_reply}')
    send_reply(username, bot_reply, whisper)


def worker_loop():
    """Process queued chat jobs one by one so the GPU is not flooded."""
    while True:
        username, clean_message, whisper = request_queue.get()
        try:
            process_ai_request(username, clean_message, whisper)
        except Exception as e:
            print(f'Ollama error: {e}')
        finally:
            request_queue.task_done()
            time.sleep(WORKER_PAUSE_SEC)


worker_thread = threading.Thread(target=worker_loop, name='ollama-worker', daemon=True)
worker_thread.start()


@On(bot, 'spawn')
def handle_spawn(*args):
    print(f'Chat bot joined Minecraft {MC_VERSION}!')
    bot.chat('/gamemode spectator')
    bot.chat(settings.spawn_greeting(_cfg))


def _on_player_chat(username, message):
    if not isinstance(message, str) or not message.startswith('.'):
        return

    print(f'{username}: {message}')

    prompt_text, whisper = parse_dot_message(message)
    if not prompt_text:
        return

    request_queue.put((username, prompt_text, whisper))
    print(f'Queued request from {username} (queue size: {request_queue.qsize()})')


chat_inbox.bind(bot, _on_player_chat)


@On(bot, 'error')
def handle_error(this, err, *args):
    print(f'Bot error: {err}')


@On(bot, 'kicked')
def handle_kicked(this, reason, *args):
    print(f'Bot was kicked: {reason}')
