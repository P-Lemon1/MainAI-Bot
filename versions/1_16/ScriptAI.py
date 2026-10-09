
from javascript import require, On
import json
import random
import re
import sys
import threading
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
collectblock = require('mineflayer-collectblock')
pvp_mod = require('mineflayer-pvp')
auto_eat_mod = require('mineflayer-auto-eat')
minecraft_data = require('minecraft-data')

# Minecraft 1.16.5 protocol
MC_VERSION = '1.16.5'

VALID_ACTIONS = ('collect', 'pvp_attack', 'follow', 'stop', 'craft', 'explore', 'none')

JSON_FALLBACK_REPLY = 'Не понял тебя, повтори короче.'
MAX_COLLECT_COUNT = 64
WORKER_PAUSE_SEC = 0.3

BLOCK_ALIASES = {
    'wood': 'oak_log',
    'tree': 'oak_log',
    'log': 'oak_log',
    'logs': 'oak_log',
    'oak': 'oak_log',
    'iron': 'iron_ore',
    'gold': 'gold_ore',
    'diamond': 'diamond_ore',
    'coal': 'coal_ore',
    'redstone': 'redstone_ore',
    'lapis': 'lapis_ore',
    'emerald': 'emerald_ore',
    'cobble': 'cobblestone',
    'dirt': 'dirt',
    'stone': 'stone',
    'sand': 'sand',
}

ITEM_ALIASES = {
    'sticks': 'stick',
    'planks': 'oak_planks',
    'wood_planks': 'oak_planks',
    'table': 'crafting_table',
    'workbench': 'crafting_table',
    'pick': 'wooden_pickaxe',
    'sword': 'wooden_sword',
}

current_follow_target = None
mc_data = None
task_cancel = threading.Event()
brain = None


def plugin_export(mod, *names):
    """Resolve .plugin / .loader / the module itself for bot.loadPlugin."""
    for name in names:
        try:
            value = getattr(mod, name, None)
        except Exception:
            value = None
        if value is not None:
            return value
    return mod


bot = mineflayer.createBot({
    'host': _cfg['mc_host'],
    'port': _cfg['mc_port'],
    'username': _cfg['bot_username'],
    'version': MC_VERSION
})

bot.loadPlugin(pathfinder.pathfinder)
bot.loadPlugin(plugin_export(collectblock, 'plugin'))
bot.loadPlugin(plugin_export(pvp_mod, 'plugin'))
bot.loadPlugin(plugin_export(auto_eat_mod, 'plugin', 'loader'))


def normalize_name(value):
    if value is None:
        return ''
    return str(value).strip().lower().replace(' ', '_')


def js_lookup(mapping, key):
    if mapping is None or not key:
        return None
    try:
        return mapping[key]
    except Exception:
        return None


def parse_count(value, default=1):
    try:
        count = int(value)
    except (TypeError, ValueError):
        return default
    if count < 1:
        return default
    return min(count, MAX_COLLECT_COUNT)


def parse_ai_response(raw_text):
    default = {
        'reply': JSON_FALLBACK_REPLY,
        'action': 'none',
        'target': '',
        'count': 1,
    }
    if not raw_text or not str(raw_text).strip():
        return default

    text = str(raw_text).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    data = None
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

    reply = data.get('reply', '')
    if not isinstance(reply, str) or not reply.strip():
        reply = JSON_FALLBACK_REPLY
    else:
        reply = reply.strip()

    action = data.get('action', 'none')
    if not isinstance(action, str) or action not in VALID_ACTIONS:
        action = 'none'

    target = data.get('target', '')
    if target is None:
        target = ''
    else:
        target = str(target).strip()

    return {
        'reply': reply,
        'action': action,
        'target': target,
        'count': parse_count(data.get('count'), 1),
    }


def player_entity(username):
    try:
        if username not in bot.players:
            return None
        return getattr(bot.players[username], 'entity', None)
    except Exception:
        return None


def iter_entities():
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


def find_entity(target_name):
    """Find a player or mob by name / minecraft id."""
    wanted = normalize_name(target_name)
    if not wanted:
        return None

    try:
        if wanted in bot.players:
            ent = player_entity(wanted)
            if ent is not None:
                return ent
    except Exception:
        pass

    best = None
    best_dist = None
    bot_pos = getattr(getattr(bot, 'entity', None), 'position', None)

    for ent in iter_entities():
        try:
            name = normalize_name(getattr(ent, 'name', ''))
            display = normalize_name(getattr(ent, 'displayName', ''))
            kind = normalize_name(getattr(ent, 'type', ''))
            if wanted not in (name, display) and not name.endswith(wanted) and wanted not in name:
                # allow "ender_dragon" vs "enderdragon"
                compact_wanted = wanted.replace('_', '')
                if compact_wanted not in (name.replace('_', ''), display.replace('_', '')):
                    continue
            if kind == 'player' and name == normalize_name(bot.username):
                continue
            if bot_pos is None:
                return ent
            pos = getattr(ent, 'position', None)
            if pos is None:
                continue
            dist = pos.distanceTo(bot_pos)
            if best is None or dist < best_dist:
                best = ent
                best_dist = dist
        except Exception:
            continue
    return best


def stop_world_tasks():
    """Cancel combat, collecting, and pathfinding. Safe to call anytime."""
    task_cancel.set()
    try:
        bot.pvp.stop()
    except Exception:
        pass
    try:
        bot.collectBlock.cancelTask()
    except Exception:
        pass
    try:
        bot.pathfinder.setGoal(None)
    except Exception:
        pass
    try:
        bot.clearControlStates()
    except Exception:
        pass


def setup_auto_eat():
    auto = getattr(bot, 'autoEat', None)
    if auto is None:
        print('auto-eat plugin is not available')
        return
    try:
        opts = getattr(auto, 'options', None)
        if opts is not None:
            try:
                opts.startAt = 14
                opts.bannedFood = []
                opts.priority = 'foodPoints'
            except Exception:
                pass
        if hasattr(auto, 'enableAuto'):
            auto.enableAuto()
        elif hasattr(auto, 'enable'):
            auto.enable()
        print('auto-eat enabled')
    except Exception as e:
        print(f'auto-eat setup error: {e}')


def resolve_block_name(target):
    key = BLOCK_ALIASES.get(normalize_name(target), normalize_name(target))
    if mc_data is None:
        return key, None
    entry = js_lookup(mc_data.blocksByName, key)
    block_id = getattr(entry, 'id', None) if entry is not None else None
    return key, block_id


def resolve_item_name(target):
    key = ITEM_ALIASES.get(normalize_name(target), normalize_name(target))
    if mc_data is None:
        return key, None
    entry = js_lookup(mc_data.itemsByName, key)
    item_id = getattr(entry, 'id', None) if entry is not None else None
    return key, item_id


def task_collect(block_name, count):
    name, block_id = resolve_block_name(block_name)
    if block_id is None:
        bot.chat(f'Не знаю блок {block_name}.')
        return

    collected = 0
    try:
        while collected < count and not task_cancel.is_set():
            block = bot.findBlock({
                'matching': block_id,
                'maxDistance': 64
            })
            if block is None:
                if collected == 0:
                    bot.chat(f'Рядом нет {name}.')
                else:
                    bot.chat(f'Собрал {collected} из {count} ({name}).')
                return
            try:
                bot.collectBlock.collect(block)
                collected += 1
                print(f'Collected {name} ({collected}/{count})')
            except Exception as e:
                print(f'collectBlock error: {e}')
                traceback.print_exc()
                bot.chat(f'Не смог добыть {name}.')
                return
    except Exception as e:
        print(f'collect task error: {e}')
        traceback.print_exc()


def task_pvp_attack(target_name):
    entity = find_entity(target_name)
    if entity is None:
        bot.chat(f'Не вижу цель: {target_name}.')
        return
    try:
        bot.pvp.attack(entity)
        print(f'PVP started vs {target_name}')
    except Exception as e:
        print(f'pvp.attack error: {e}')
        traceback.print_exc()
        bot.chat('Не получилось начать бой.')


def task_follow(username):
    entity = player_entity(username)
    if entity is None:
        bot.chat('Не вижу тебя, подойди ближе.')
        return
    try:
        goal = pathfinder.goals.GoalFollow(entity, 2)
        bot.pathfinder.setGoal(goal, True)
        print(f'Action: follow {username}')
    except Exception as e:
        print(f'follow error: {e}')
        traceback.print_exc()


def task_craft(item_name, count):
    name, item_id = resolve_item_name(item_name)
    if item_id is None:
        bot.chat(f'Не знаю предмет {item_name}.')
        return

    table = None
    table_id = None
    if mc_data is not None:
        table_entry = js_lookup(mc_data.blocksByName, 'crafting_table')
        table_id = getattr(table_entry, 'id', None) if table_entry is not None else None
    if table_id is not None:
        try:
            table = bot.findBlock({
                'matching': table_id,
                'maxDistance': 32
            })
        except Exception:
            table = None

    try:
        recipes = bot.recipesFor(item_id, None, 1, table)
    except Exception as e:
        print(f'recipesFor error: {e}')
        recipes = None

    recipe = None
    try:
        if recipes is not None and len(list(recipes)) > 0:
            recipe = recipes[0]
    except Exception:
        try:
            recipe = recipes[0]
        except Exception:
            recipe = None

    if recipe is None:
        bot.chat(f'Нет рецепта или не хватает ресурсов для {name}.')
        return

    try:
        bot.craft(recipe, count, table)
        print(f'Crafted {name} x{count}')
    except Exception as e:
        print(f'craft error: {e}')
        traceback.print_exc()
        bot.chat(f'Не смог скрафтить {name}.')


def apply_action(action, username, target, count):
    """Start a world action. Long jobs stay on the worker thread, JS physics stays free."""
    global current_follow_target

    if action == 'none':
        return

    if action == 'stop':
        current_follow_target = None
        stop_world_tasks()
        print('Action: stop all tasks')
        return

    # New job replaces the previous one
    stop_world_tasks()
    task_cancel.clear()

    try:
        if action == 'follow':
            who = target or username
            current_follow_target = who
            task_follow(who)

        elif action == 'collect':
            current_follow_target = None
            if not target:
                bot.chat('Какой блок добывать?')
                return
            task_collect(target, count)

        elif action == 'pvp_attack':
            current_follow_target = None
            if not target:
                bot.chat('Кого атаковать?')
                return
            task_pvp_attack(target)

        elif action == 'craft':
            if not target:
                bot.chat('Что крафтить?')
                return
            task_craft(target, count)

        elif action == 'explore':
            task_explore()

    except Exception as e:
        print(f'Action handler error ({action}): {e}')
        traceback.print_exc()


def task_explore():
    try:
        pos = bot.entity.position
        dx = random.choice((-22, -16, -12, 12, 16, 22))
        dz = random.choice((-22, -16, -12, 12, 16, 22))
        goal = pathfinder.goals.GoalNear(
            int(pos.x) + dx, int(pos.y), int(pos.z) + dz, 2
        )
        bot.pathfinder.setGoal(goal)
        print('Action: explore')
    except Exception as e:
        print(f'explore error: {e}')
        traceback.print_exc()


def brain_speak(text):
    if text:
        bot.chat(str(text)[:256])


def brain_state():
    return {'following': current_follow_target}


def brain_stop():
    global current_follow_target
    current_follow_target = None
    stop_world_tasks()


brain = companion_brain.CompanionBrain(
    bot,
    mode='survival',
    apply_action=apply_action,
    speak=brain_speak,
    extra_state=brain_state,
    on_stop=brain_stop,
)


@On(bot, 'spawn')
def handle_spawn(*args):
    global mc_data
    print(f'Bot successfully joined Minecraft {MC_VERSION}!')
    try:
        mc_data = minecraft_data(bot.version)
    except Exception as e:
        print(f'minecraft-data error: {e}')
        mc_data = None

    try:
        movements = pathfinder.Movements(bot)
        movements.canDig = True
        movements.maxDropDown = 4
        try:
            movements.allow180Inertia = False
        except Exception:
            pass
        bot.pathfinder.setMovements(movements)
    except Exception as e:
        print(f'Pathfinder setup error: {e}')

    setup_auto_eat()
    if brain is not None:
        brain.start()
    bot.chat('Привет! Я сам решаю, что делать: добывать, крафтить, драться и ходить с тобой. Можешь просто дать приказ в чат.')


@On(bot, 'chat')
def handle_chat(this, username, message, *args):
    if username == str(bot.username):
        return
    if not isinstance(message, str):
        return

    print(f'{username}: {message}')
    if brain is not None:
        brain.enqueue_chat(username, message)


@On(bot, 'entityHurt')
def handle_hurt(this, entity, *args):
    try:
        if entity is None or bot.entity is None:
            return
        if getattr(entity, 'id', None) != getattr(bot.entity, 'id', None):
            return
        attacker = find_entity_nearby_hostile()
        if attacker is None:
            return
        print('Bot was hit, starting PVP')
        bot.pvp.attack(attacker)
    except Exception as e:
        print(f'Hurt handler error: {e}')


def find_entity_nearby_hostile():
    bot_pos = getattr(getattr(bot, 'entity', None), 'position', None)
    if bot_pos is None:
        return None
    best = None
    best_dist = None
    for ent in iter_entities():
        try:
            kind = getattr(ent, 'type', None)
            if kind not in ('mob', 'monster'):
                continue
            pos = getattr(ent, 'position', None)
            if pos is None:
                continue
            dist = pos.distanceTo(bot_pos)
            if dist > 6:
                continue
            if best is None or dist < best_dist:
                best = ent
                best_dist = dist
        except Exception:
            continue
    return best


@On(bot, 'error')
def handle_error(this, err, *args):
    print(f'Bot error: {err}')


@On(bot, 'kicked')
def handle_kicked(this, reason, *args):
    print(f'Bot was kicked: {reason}')
