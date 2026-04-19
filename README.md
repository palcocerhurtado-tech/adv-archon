# ADV ARCHON

ADV ARCHON is a private, local-first terminal assistant built for macOS. It lives on Pablo's Mac, reads local files, uses Gemini or Ollama, and keeps the interaction transparent by showing every tool call it makes.

CLI commands:

- `adv-archon`
- `adv`

## Block 5 status

This repository currently includes:

- Conversational REPL with `rich` and `prompt_toolkit`
- One-shot CLI mode
- Lightweight agent loop with tool dispatch
- Gemini cloud routing
- Ollama local fallback routing
- Local and web tools: `read_file`, `list_dir`, `web_search`, `web_fetch`
- Safe execution tools: `shell_exec`, `python_exec`, `clipboard_read`, `clipboard_write`, `open_app`
- Runtime context awareness: cwd, git state, and project working set
- Long-term memory backed by SQLite and local embeddings
- Session cost ledger and local JSON logs
- Auto mode with confirmation before enabling
- Optional PII redaction before cloud LLM calls
- `adv-archon daily` proactive routine
- Voice output with macOS `say`
- Local dictation with `faster-whisper`
- Optional wake-word startup flow with `--listen`
- Install and uninstall scripts for a global `adv-archon` command

## Quick start

1. Install dependencies with `uv sync --dev`
2. Copy `.env.example` values into `~/.adv-archon/.env`
3. Run `uv run adv-archon`

## Usage

Interactive mode:

```bash
adv-archon
```

Short alias:

```bash
adv
```

Interactive mode with auto execution:

```bash
adv-archon --auto
```

Interactive mode with startup dictation:

```bash
adv-archon --listen
```

One-shot mode:

```bash
adv-archon "¿Qué hace este script?" /path/to/file.py
```

Daily routine:

```bash
adv-archon daily
```

## Current slash commands

- `/help`
- `/exit`
- `/mode <cloud|local>`
- `/read <path>`
- `/web <query>`
- `/recall <query>`
- `/forget <query|id>`
- `/cost`
- `/log [n]`
- `/auto [on|off|status]`
- `/voice [on|off|status]`
- `/listen`
- `/run <cmd>`
- `/python <code>`

## Memory

Long-term memory is stored in `~/.adv-archon/memory.db`. ADV ARCHON can recall relevant facts into a turn and also save stable user facts when asked.

Incognito mode disables persistence for sessions, logs, and memory writes:

```bash
adv-archon --incognito
```

## Privacy

ADV ARCHON only uses the network for Gemini, DuckDuckGo search, and URL fetching when those actions are needed.

Optional cloud PII redaction can be enabled in `~/.adv-archon/config.toml`:

```toml
[privacy]
redact_cloud_pii = true
```

When enabled, ADV ARCHON replaces emails, phones, IBANs, and Spanish DNI/NIE identifiers with placeholders before sending cloud prompts, then restores them in the answer.

## Voice

Voice output is backed by macOS `say`, so no extra system package is needed for TTS.

Dictation uses local Whisper via `faster-whisper`. It records from the microphone, transcribes in Spanish by default, and injects the text back into the REPL.

Example config:

```toml
[voice]
enabled = false
say_voice = "Jorge"
rate_wpm = 190
stt_model = "small"
stt_language = "es"
wake_word_enabled = false
wake_word_keyword = "jarvis"
```

Optional wake-word mode requires `pvporcupine` plus `PORCUPINE_ACCESS_KEY`.

## Command safety

- Read-only shell commands in the whitelist run without prompt.
- Other shell commands ask for confirmation by default.
- `--auto` or `/auto on` disables those prompts for non-destructive shell commands after a separate confirmation step.
- Dangerous commands such as `rm`, `sudo`, `git reset --hard`, `git clean`, and `curl | sh` are always confirmed.
