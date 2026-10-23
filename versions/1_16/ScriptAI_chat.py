
from javascript import require, On
import json
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

# Minecraft 1.16.5 protocol
MC_VERSION = '1.16.5'

SYSTEM_PROMPT_CHAT = (
    'You are a friendly AI companion in Minecraft chat. '
    'Reply with a short, natural sentence in Russian. '
    'Plain text only — no JSON, no markdown, no code fences, no actions.'
)

SYSTEM_PROMPT_OPERATION = (
    'You are a Minecraft operator assistant. '
    'You MUST answer with STRICT JSON only. No markdown, no code fences, no extra text.\n'
    'JSON format:\n'
    '{"command": "<minecraft command, usually starting with />", '
    '"reply": "<short natural sentence in Russian>"}\n'
    'Rules:\n'
    '- "command" is executed in-game as-is (example: /give PlayerName iron_sword 1).\n'
    '- Use the player name from the user message when the command needs a target.\n'
    '- "reply" is a short confirmation spoken back to the player.\n'
    '- Never output anything except the JSON object.'
)

FALLBACK_REPLY = 'Не понял тебя, повтори короче.'
MAX_HISTORY = 15
WORKER_PAUSE_SEC = 0.8

# Any {...} tag in the raw message
BRACE_RE = re.compile(r'\{([^}]+)\}')

# Valid tags inside braces, case-insensitive, mapped to flag names
SUPPORTED_ARGS = {
    '-m': 'message',
    '-message': 'message',
    '-c': 'clear',
    '-clear': 'clear',
    '-o': 'operation',
    '-operation': 'operation',
}

chat_history = []
history_lock = threading.Lock()
request_queue = queue.Queue()


bot = mineflayer.createBot({
    'host': _cfg['mc_host'],
    'port': _cfg['mc_port'],
    'username': _cfg['bot_username'],
    'version': MC_VERSION
})


def send_whisper(username, text):
    """Reply in private chat. Prefer bot.whisper, fall back to /msg."""
    message = str(text).strip()
    if not message:
        return
    if len(message) > 240:
        message = message[:240]
    try:
        bot.whisper(username, message)
    except Exception:
        bot.chat(f'/msg {username} {message}')


def send_reply(username, reply, whisper):
    text = str(reply).strip() or FALLBACK_REPLY
    if len(text) > 240:
        text = text[:240]
    if whisper:
        send_whisper(username, text)
    else:
        bot.chat(text)


def parse_command(raw_after_dot):
    """
    Validate all {tags}, collect flags, strip valid tags from the prompt.
    Returns (clean_text, flags, invalid_tag).
    invalid_tag is the original '{...}' string if a tag is not supported.
    """
    flags = {
        'message': False,
        'clear': False,
        'operation': False,
    }

    for match in BRACE_RE.finditer(raw_after_dot):
        inner = match.group(1).strip().lower()
        if inner not in SUPPORTED_ARGS:
            return None, flags, match.group(0)
        flags[SUPPORTED_ARGS[inner]] = True

    clean = BRACE_RE.sub(' ', raw_after_dot)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean, flags, None


def clear_history():
    global chat_history
    with history_lock:
        chat_history = []
    print('Context history cleared')


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


def parse_operation_json(raw_text):
    """Parse {command, reply} from the model. Never raises."""
    default = {'command': None, 'reply': FALLBACK_REPLY}
    if not raw_text or not str(raw_text).strip():
        return default

    text = str(raw_text).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return default
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return default

    if not isinstance(data, dict):
        return default

    command = data.get('command')
    reply = data.get('reply', '')
    if not isinstance(reply, str) or not reply.strip():
        reply = FALLBACK_REPLY
    if command is not None:
        command = str(command).strip() or None

    return {'command': command, 'reply': reply.strip()}


def call_ollama(system_prompt, username, clean_message, force_json=False):
    try:
        return llm_client.complete_messages(
            _cfg,
            [
                {'role': 'system', 'content': system_prompt},
                *snapshot_history(),
                {'role': 'user', 'content': f'{username}: {clean_message}'},
            ],
            json_mode=force_json,
            timeout=20,
        )
    except Exception as e:
        print(f'LLM error: {e}')
        return None


def process_ai_request(username, clean_message, whisper, clear, operation):
    """One queued job: optional clear, then one Ollama call, then chat/command."""
    if clear:
        clear_history()

    if not clean_message:
        if clear:
            send_reply(username, 'Контекст очищен.', whisper)
        return

    append_history('user', f'{username}: {clean_message}')

    if operation:
        raw_reply = call_ollama(
            SYSTEM_PROMPT_OPERATION,
            username,
            clean_message,
            force_json=True
        )
        if raw_reply is None:
            return

        parsed = parse_operation_json(raw_reply)
        command = parsed['command']
        bot_reply = parsed['reply']

        if command:
            print(f'Execute command: {command}')
            bot.chat(command)

        append_history('assistant', bot_reply)
        mode = 'whisper' if whisper else 'chat'
        print(f'AI_Partner [{mode}/op]: {bot_reply}')
        send_reply(username, bot_reply, whisper)
        return

    raw_reply = call_ollama(SYSTEM_PROMPT_CHAT, username, clean_message, force_json=False)
    if raw_reply is None:
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
        job = request_queue.get()
        try:
            process_ai_request(*job)
        except Exception as e:
            print(f'Ollama error: {e}')
        finally:
            request_queue.task_done()
            time.sleep(WORKER_PAUSE_SEC)


def enqueue_user_message(username, message, from_whisper):
    if username == str(bot.username):
        return
    if not isinstance(message, str) or not message.startswith('.'):
        return

    print(f'{username} [{"whisper" if from_whisper else "chat"}]: {message}')

    clean_text, flags, invalid_tag = parse_command(message[1:])
    if invalid_tag is not None:
        print(f'Rejected unknown argument from {username}: {invalid_tag}')
        send_whisper(username, f'Unknown argument: {invalid_tag}')
        return

    whisper = flags['message']
    request_queue.put((username, clean_text, whisper, flags['clear'], flags['operation']))
    print(f'Queued request from {username} (queue size: {request_queue.qsize()})')


worker_thread = threading.Thread(target=worker_loop, name='ollama-worker', daemon=True)
worker_thread.start()


@On(bot, 'spawn')
def handle_spawn(*args):
    print(f'Chat bot joined Minecraft {MC_VERSION}!')
    bot.chat('/gamemode spectator')
    bot.chat(settings.spawn_greeting(_cfg))


chat_inbox.bind(bot, lambda username, message: enqueue_user_message(username, message, False))


@On(bot, 'error')
def handle_error(this, err, *args):
    print(f'Bot error: {err}')


@On(bot, 'kicked')
def handle_kicked(this, reason, *args):
    print(f'Bot was kicked: {reason}')
