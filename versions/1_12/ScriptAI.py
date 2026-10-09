
from javascript import require, On
import json
import random
import re
import sys
import time
import traceback
from pathlib import Path

_MINEAI = Path(__file__).resolve().parents[2]
if str(_MINEAI) not in sys.path:
    sys.path.insert(0, str(_MINEAI))
import companion_brain
import settings

_cfg = settings.require_config()
companion_brain.configure(_cfg)

mineflayer = require('mineflayer')
pathfinder = require('mineflayer-pathfinder')

# Vanilla 1.12.0 protocol (335). Do not use 1.12.2 here — that server will reject it.
MC_VERSION = '1.12'

VALID_ACTIONS = (
    'follow', 'stop', 'mine_tree', 'look', 'jump',
    'drop_item', 'attack', 'step_back', 'step_forward', 'explore', 'none'
)

JSON_FALLBACK_REPLY = 'Не понял тебя, повтори короче.'


bot = mineflayer.createBot({
    'host': _cfg['mc_host'],
    'port': _cfg['mc_port'],
    'username': _cfg['bot_username'],
    'version': MC_VERSION,
    'hideErrors': False,
    'checkTimeoutInterval': 60 * 1000
})

bot.loadPlugin(pathfinder.pathfinder)

current_follow_target = None
last_attacker = None
physics_tick_counter = 0
brain = None


def format_js_error(err):
    """Turn a JS / ChatMessage error into a readable string."""
    if err is None:
        return 'unknown'
    try:
        if hasattr(err, 'toString'):
            text = err.toString()
            if text:
                return str(text)
    except Exception:
        pass
    try:
        stack = getattr(err, 'stack', None)
        if stack:
            return str(stack)
    except Exception:
        pass
    try:
        return str(err)
    except Exception:
        return '<unprintable error>'


def safe_chat(text):
    """Send chat without crashing the 1.12 client if the packet fails."""
    if text is None:
        return
    message = str(text)
    if not message:
        return
    # 1.12 vanilla client chat limit is 256 characters
    if len(message) > 256:
        message = message[:256]
    try:
        bot.chat(message)
    except Exception as e:
        print(f'Chat send error: {e}')


def iter_entities():
    """Safely walk bot.entities (JS object) from Python."""
    try:
        entities = bot.entities
        if entities is None:
            return
        try:
            ids = list(entities)
        except Exception:
            try:
                ids = list(entities.keys())
            except Exception:
                return
        for eid in ids:
            try:
                ent = entities[eid]
            except Exception:
                continue
            if ent is not None:
                yield ent
    except Exception as e:
        print(f'Entity scan error: {e}')


def parse_ai_response(raw_text):
    default = {'reply': JSON_FALLBACK_REPLY, 'action': 'none'}
    if not raw_text or not str(raw_text).strip():
        return default

    text = str(raw_text).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return default
        else:
            return default

    if not isinstance(data, dict):
        return default

    reply = data.get('reply', '').strip() or JSON_FALLBACK_REPLY
    action = data.get('action', 'none')
    if action not in VALID_ACTIONS:
        action = 'none'

    return {'reply': reply, 'action': action}


def is_log_block(block):
    """1.12 wood IDs are log / log2, not oak_log etc."""
    if not block or not getattr(block, 'name', None):
        return False
    name = str(block.name)
    return name in ('log', 'log2') or 'log' in name


def apply_action(action, username, target='', count=1):
    global current_follow_target, last_attacker
    try:
        who = (target or username or '')
        player = bot.players[who] if who and who in bot.players else None
        if player is None and username and username in bot.players:
            player = bot.players[username]
        entity = getattr(player, 'entity', None) if player is not None else None

        if action == 'follow':
            if entity:
                current_follow_target = who or username
                goal = pathfinder.goals.GoalFollow(entity, 2)
                bot.pathfinder.setGoal(goal, True)
                print(f'Action: follow {current_follow_target}')

        elif action == 'stop':
            current_follow_target = None
            bot.pathfinder.setGoal(None)
            bot.clearControlStates()
            print('Action: stop pathfinding')

        elif action == 'step_back':
            bot.pathfinder.setGoal(None)
            bot.setControlState('back', True)
            time.sleep(0.8)
            bot.setControlState('back', False)
            if current_follow_target and current_follow_target in bot.players:
                p_entity = getattr(bot.players[current_follow_target], 'entity', None)
                if p_entity:
                    bot.pathfinder.setGoal(pathfinder.goals.GoalFollow(p_entity, 2), True)

        elif action == 'step_forward':
            bot.pathfinder.setGoal(None)
            bot.setControlState('forward', True)
            time.sleep(0.8)
            bot.setControlState('forward', False)

        elif action == 'attack':
            target = last_attacker if last_attacker else entity
            if target:
                bot.attack(target)

        elif action == 'look':
            if entity:
                bot.lookAt(entity.position.offset(0, 1.6, 0))

        elif action == 'jump':
            bot.setControlState('jump', True)
            bot.setControlState('jump', False)

        elif action == 'drop_item':
            held_item = bot.heldItem
            if held_item:
                bot.tossStack(held_item)

        elif action == 'mine_tree':
            wood_blocks = bot.findBlocks({
                'matching': is_log_block,
                'maxDistance': 15,
                'count': 1
            })
            if wood_blocks:
                target_pos = wood_blocks[0]
                bot.pathfinder.setGoal(pathfinder.goals.GoalGetToBlock(target_pos.x, target_pos.y, target_pos.z))

        elif action == 'explore':
            pos = bot.entity.position
            dx = random.choice((-18, -12, 12, 18))
            dz = random.choice((-18, -12, 12, 18))
            bot.pathfinder.setGoal(
                pathfinder.goals.GoalNear(int(pos.x) + dx, int(pos.y), int(pos.z) + dz, 2)
            )
            print('Action: explore')

    except Exception as e:
        print(f'Action handler error ({action}): {e}')
        traceback.print_exc()


def brain_speak(text):
    if text:
        safe_chat(text)


def brain_state():
    return {'following': current_follow_target}


def brain_stop():
    global current_follow_target
    current_follow_target = None
    try:
        bot.pathfinder.setGoal(None)
        bot.clearControlStates()
    except Exception:
        pass


brain = companion_brain.CompanionBrain(
    bot,
    mode='simple',
    apply_action=apply_action,
    speak=brain_speak,
    extra_state=brain_state,
    on_stop=brain_stop,
)


@On(bot, 'physicsTick')
def handle_physics(*args):
    global current_follow_target, last_attacker, physics_tick_counter

    # Do not run Python entity scans every tick — that freezes keep-alives on 1.12
    physics_tick_counter += 1
    if physics_tick_counter % 15 != 0:
        return

    try:
        if not bot.entity:
            return

        bot_id = getattr(bot.entity, 'id', None)
        bot_pos = getattr(bot.entity, 'position', None)
        if bot_pos is None:
            return

        for ent in iter_entities():
            try:
                if getattr(ent, 'id', None) == bot_id:
                    continue
                if getattr(ent, 'type', None) not in ('mob', 'monster'):
                    continue
                pos = getattr(ent, 'position', None)
                if pos is None:
                    continue
                dist = pos.distanceTo(bot_pos)
                if dist < 3.0:
                    print(f'Опасность! Моб {getattr(ent, "name", "?")} слишком близко, отбиваемся!')
                    bot.lookAt(pos.offset(0, 1.2, 0))
                    bot.attack(ent)
                    if current_follow_target and current_follow_target in bot.players:
                        p_entity = getattr(bot.players[current_follow_target], 'entity', None)
                        if p_entity:
                            bot.pathfinder.setGoal(pathfinder.goals.GoalFollow(p_entity, 2), True)
                    break
            except Exception:
                continue
    except Exception as e:
        print(f'Physics tick error: {e}')


@On(bot, 'entityHurt')
def handle_hurt(this, entity, *args):
    global last_attacker
    try:
        if entity is None or bot.entity is None:
            return
        if getattr(entity, 'id', None) != getattr(bot.entity, 'id', None):
            return

        print('Бота кто-то ударил!')
        bot_pos = getattr(bot.entity, 'position', None)
        if bot_pos is None:
            return

        for ent in iter_entities():
            try:
                if getattr(ent, 'id', None) == getattr(bot.entity, 'id', None):
                    continue
                pos = getattr(ent, 'position', None)
                if pos is None:
                    continue
                if pos.distanceTo(bot_pos) < 4:
                    last_attacker = ent
                    bot.attack(ent)
                    break
            except Exception:
                continue
    except Exception as e:
        print(f'Hurt handler error: {e}')


@On(bot, 'login')
def handle_login(*args):
    print(f'Logged in to Minecraft {MC_VERSION}')


@On(bot, 'spawn')
def handle_spawn(*args):
    print(f'Bot successfully joined Minecraft {MC_VERSION}!')
    try:
        movements = pathfinder.Movements(bot)
        movements.canDig = False
        movements.maxDropDown = 3
        try:
            movements.allow180Inertia = False
        except Exception:
            pass
        bot.pathfinder.setMovements(movements)
    except Exception as e:
        print(f'Pathfinder setup error (bot stays online): {e}')
        traceback.print_exc()

    if brain is not None:
        brain.start()
    try:
        safe_chat('Ya sam reshayu chto delat. Pishi prikaz v chat.')
    except Exception as e:
        print(f'Spawn chat error: {e}')


@On(bot, 'error')
def handle_error(this, err, *args):
    print(f'Bot error: {format_js_error(err)}')


@On(bot, 'kicked')
def handle_kicked(this, reason, *args):
    print(f'Bot was kicked: {format_js_error(reason)}')


@On(bot, 'end')
def handle_end(this, reason, *args):
    print(f'Bot disconnected: {format_js_error(reason)}')


@On(bot, 'chat')
def handle_chat(this, username, message, *args):
    if username == str(bot.username):
        return

    print(f'{username}: {message}')
    if brain is not None:
        brain.enqueue_chat(username, message)
