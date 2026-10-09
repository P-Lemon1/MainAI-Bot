
from javascript import require, On
import json
import random
import re
import sys
import time
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

# Minecraft 1.21.4 protocol
MC_VERSION = '1.21.4'

VALID_ACTIONS = (
    'follow', 'stop', 'mine_tree', 'look', 'jump',
    'drop_item', 'attack', 'step_back', 'step_forward', 'explore', 'none'
)

JSON_FALLBACK_REPLY = 'Не понял тебя, повтори короче.'

bot = mineflayer.createBot({
    'host': _cfg['mc_host'],
    'port': _cfg['mc_port'],
    'username': _cfg['bot_username'],
    'version': MC_VERSION
})

bot.loadPlugin(pathfinder.pathfinder)

current_follow_target = None
last_attacker = None
brain = None


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
                'matching': lambda b: b and 'log' in b.name,
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


def brain_speak(text):
    if text:
        bot.chat(str(text)[:256])


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
    global current_follow_target, last_attacker

    if not bot.entity:
        return

    # Проверка враждебных мобов неподалёку
    for name in bot.entities:
        ent = bot.entities[name]
        if ent and ent != bot.entity and ent.type in ('mob', 'monster'):
            dist = ent.position.distanceTo(bot.entity.position)
            if dist < 3.0:
                print(f'Опасность! Моб {ent.name} слишком близко, отбиваемся!')
                bot.lookAt(ent.position.offset(0, 1.2, 0))
                bot.attack(ent)
                if current_follow_target and current_follow_target in bot.players:
                    p_entity = getattr(bot.players[current_follow_target], 'entity', None)
                    if p_entity:
                        bot.pathfinder.setGoal(pathfinder.goals.GoalFollow(p_entity, 2), True)
                break


@On(bot, 'entityHurt')
def handle_hurt(this, entity, *args):
    global last_attacker
    if entity == bot.entity:
        print('Бота кто-то ударил!')
        for name in bot.entities:
            ent = bot.entities[name]
            if ent and ent != bot.entity and ent.position.distanceTo(bot.entity.position) < 4:
                last_attacker = ent
                bot.attack(ent)
                break


@On(bot, 'spawn')
def handle_spawn(*args):
    print(f'Bot successfully joined Minecraft {MC_VERSION}!')
    movements = pathfinder.Movements(bot)
    
    movements.canDig = False          
    movements.allow180Inertia = False 
    movements.maxDropDown = 3         # Ограничение высоты падения (чтобы не прыгал в обрывы)
    
    bot.pathfinder.setMovements(movements)
    if brain is not None:
        brain.start()
    bot.chat('Привет! Я сам выбираю, что делать. Можешь дать приказ в чат.')


@On(bot, 'chat')
def handle_chat(this, username, message, *args):
    if username == str(bot.username):
        return

    print(f'{username}: {message}')
    if brain is not None:
        brain.enqueue_chat(username, message)