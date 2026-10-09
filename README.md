# MainAI-Bot

Mineflayer bots with a local **Ollama** brain. A setup wizard asks for the Minecraft version, the Ollama port, the server port, and the other values the bot needs.

Боты Mineflayer с локальной нейросетью **Ollama**. Мастер настройки спрашивает версию Minecraft, порт Ollama, порт сервера и остальные нужные поля.

---

## English

### What it does

- **Companion** (`ScriptAI.py`) — the model keeps deciding what to do from world state (walk, follow, mine, fight). Player chat is a standing order. Stop words: `stop`, `стой`, `хватит`.
- **Chat spectator** (`ScriptAI_chat.py`) — sits in spectator and answers lines that start with `.` (example: `.hello`). `{ -m }` whispers the reply.

Versions: **1.12**, **1.16.5** (survival: collect / craft / PvP), **1.20.1**, **1.21.4**, **1.21.6**.

Use protocol **1.12**, not 1.12.2.

Default model: `qwen2.5-coder:14b` via Ollama (`/api/chat`).

In-game chat from the bot is Russian. Minecraft ids in actions stay English (`oak_log`, `zombie`, …).

### Requirements

| Need | Why |
| --- | --- |
| **Python 3.10+** | Wizard, brain, Mineflayer bridge (`javascript` package) |
| **Node.js 18+** | `mineflayer` and plugins |
| **Ollama** | Local LLM. Pull a model first: `ollama pull qwen2.5-coder:14b` |
| **Minecraft server** | Same version as the bot. For a nickname login set `online-mode=false` (or use an offline/cracked server) |

Python packages: `javascript`, `requests`  
Node packages: `mineflayer`, `mineflayer-pathfinder`, plus for 1.16.5: `mineflayer-collectblock`, `mineflayer-pvp`, `mineflayer-auto-eat`, `minecraft-data`

### Setup

```bash
git clone https://github.com/P-Lemon1/MainAI-Bot.git
cd MainAI-Bot
```

Windows: double-click `wizard.bat`, or:

```bash
python wizard.py
```

The wizard asks:

1. Language (English / Русский)
2. Minecraft version (`1.12` / `1.16.5` / `1.20.1` / `1.21.4` / `1.21.6`)
3. Bot type (companion or chat spectator)
4. Minecraft host (default `localhost`)
5. Minecraft server port (default `25565`)
6. Bot username (offline nick)
7. Ollama host (default `127.0.0.1`)
8. Ollama port (default `11434`)
9. Ollama model (default `qwen2.5-coder:14b`)

Then it can install `pip` + `npm` dependencies, ping Ollama, and start the bot.

Settings are saved to `config.json` (not committed). Copy `config.example.json` if you want to edit by hand.

### Run

```bash
python run.py
```

Or `run.bat` on Windows.

Start Ollama and the Minecraft server before the bot.

```bash
ollama serve
ollama pull qwen2.5-coder:14b
```

### Project layout

```
wizard.py              setup wizard
run.py                 start bot from config.json
settings.py            load / save config
companion_brain.py     autonomous Ollama loop
versions/1_12/         simple companion + chat bot
versions/1_16/         survival companion + chat bot
versions/1_20_1/
versions/1_21_4/
versions/1_21_6/
```

### Chat commands (companion)

Write in normal game chat. Examples: `follow me`, `иди за мной`, `stop`.  
Chat spectator: `.привет` or `.hello {-m}` for a whisper.

---

## Русский

### Что это

- **Компаньон** (`ScriptAI.py`) — модель сама решает, что делать по миру (ходить, следовать, добывать, драться). Сообщение игрока в чате — приказ, пока не скажут стоп (`stop`, `стой`, `хватит`).
- **Чат-зритель** (`ScriptAI_chat.py`) — в режиме наблюдателя отвечает на строки с точки: `.привет`. Тег `{ -m }` шлёт ответ шёпотом.

Версии: **1.12**, **1.16.5** (выживание: добыча / крафт / PvP), **1.20.1**, **1.21.4**, **1.21.6**.

Для 1.12 нужен протокол **1.12**, не 1.12.2.

Модель по умолчанию: `qwen2.5-coder:14b` через Ollama.

Ответы бота в чате — на русском. Идентификаторы блоков и мобов в действиях — английские.

### Что нужно

| Нужно | Зачем |
| --- | --- |
| **Python 3.10+** | Мастер, мозг, мост к Mineflayer |
| **Node.js 18+** | `mineflayer` и плагины |
| **Ollama** | Локальная модель. Сначала: `ollama pull qwen2.5-coder:14b` |
| **Сервер Minecraft** | Та же версия, что у бота. Для входа по нику: `online-mode=false` |

### Установка

```bash
git clone https://github.com/P-Lemon1/MainAI-Bot.git
cd MainAI-Bot
python wizard.py
```

На Windows можно запустить `wizard.bat`.

Мастер спрашивает:

1. Язык
2. Версию Minecraft
3. Тип бота (компаньон или чат-зритель)
4. Хост сервера (по умолчанию `localhost`)
5. Порт сервера (по умолчанию `25565`)
6. Ник бота
7. Хост Ollama (по умолчанию `127.0.0.1`)
8. Порт Ollama (по умолчанию `11434`)
9. Имя модели Ollama

Дальше можно поставить зависимости (`pip` + `npm`), проверить Ollama и сразу запустить бота.

Настройки пишутся в `config.json`. Пример: `config.example.json`.

### Запуск

```bash
python run.py
```

Или `run.bat`. Сначала подними Ollama и Minecraft-сервер.

### Лицензия

MIT — see [LICENSE](LICENSE).
