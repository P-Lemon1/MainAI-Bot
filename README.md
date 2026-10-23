# MainAI-Bot

Mineflayer bots with a **local LLM**. The wizard finds AI studios on this PC (Ollama, LM Studio, llama.cpp, KoboldCPP, Jan, GPT4All, or any OpenAI-compatible port), lets you pick one if several are installed, then lists that studio's models.

Боты Mineflayer с **локальной нейросетью**. Мастер сам находит ИИ-студии на компьютере (Ollama, LM Studio, llama.cpp, KoboldCPP, Jan, GPT4All или любой порт с OpenAI API), если их несколько — спрашивает какую взять, затем показывает модели этой студии.

Works the same on any Windows 11 PC: no hardcoded username, disk letter, or model folder. Paths come from `%LOCALAPPDATA%`, `%USERPROFILE%`, `PATH`, running processes, and HTTP probes.

На любом Windows 11 работает одинаково: нет жёстких путей вида `D:\…` или чужого ника. Поиск идёт через стандартные папки, `PATH`, процессы и HTTP.

---

## English

### What it does

- **Companion** (`ScriptAI.py`) — the model keeps deciding what to do from world state (walk, follow, mine, fight). Player chat is a standing order. Stop words: `stop`, `стой`, `хватит`.
- **Chat spectator** (`ScriptAI_chat.py`) — sits in spectator and answers lines that start with `.` (example: `.hello`). `{ -m }` whispers the reply.

Versions: **1.12**, **1.16.5** (survival: collect / craft / PvP), **1.20.1**, **1.21.4**, **1.21.6**.

Use protocol **1.12**, not 1.12.2.

On join the bot says `Hello, I am {name}, your companion.` (or chat bot), using the wizard language and nick.

Mineflayer is a **vanilla** client. A Fabric/Forge LAN world with extra mods will kick the bot.

### Requirements

| Need | Why |
| --- | --- |
| **Python 3.10+** | Wizard, brain, Mineflayer bridge (`javascript` package) |
| **Node.js 18+** | `mineflayer` and plugins |
| **A local LLM studio** | Ollama, LM Studio, llama.cpp server, etc. At least one model loaded |
| **Minecraft server** | Same version as the bot. For a nickname login set `online-mode=false` |

The wizard talks to:

- Ollama: `GET /api/tags`, `POST /api/chat`
- LM Studio / llama.cpp / Jan / GPT4All / KoboldCPP: `GET /v1/models`, `POST /v1/chat/completions`

If the studio is installed but the server is off, start it (Ollama tray, LM Studio local server, `llama-server`, …) and scan again.

### Setup

```bash
git clone https://github.com/P-Lemon1/MainAI-Bot.git
cd MainAI-Bot
python wizard.py
```

Windows: `wizard.bat`.

The wizard asks:

1. Language (English / Русский)
2. Minecraft version
3. Bot type (companion or chat spectator)
4. Minecraft host (default `localhost`)
5. Minecraft server port (default `25565` — LAN Open-to-LAN uses the port shown in chat)
6. Bot username
7. AI studio — auto-detected; pick one if several exist
8. Model from that studio's list

Then it can install `pip` + `npm` dependencies and start the bot.

Settings go to `config.json` (gitignored). Example: `config.example.json`.

### Run

```bash
python run.py
```

Or `run.bat`. Start the LLM studio and the Minecraft world first.

### Tests

```bash
python -m unittest tests.test_llm -v
python selfcheck.py
```

---

## Русский

### Что это

- **Компаньон** — модель сама ходит, следует, добывает, дерётся. Сообщение в чате — приказ, пока не скажут `stop` / `стой` / `хватит`.
- **Чат-зритель** — в наблюдателе отвечает на строки с точки: `.привет`.

При входе: `Привет, я {ник}, твой компаньон.` или `…твой чат-бот.`

Нужен **ванильный** сервер/мир той же версии. Fabric с модами бота выкинет.

### Установка

```bash
git clone https://github.com/P-Lemon1/MainAI-Bot.git
cd MainAI-Bot
python wizard.py
```

Мастер сам ищет Ollama, LM Studio, llama.cpp и другие локальные API. Если студий несколько — выбираешь одну, затем модель.

Запуск: `python run.py`. Сначала подними ИИ-студию и Minecraft.

### Лицензия

MIT — see [LICENSE](LICENSE).
