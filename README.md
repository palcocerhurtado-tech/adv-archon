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
- Intent auto-router for chat, code, docs, web, shell, and assistant tasks
- Structured long-term memory backed by SQLite and local embeddings
- Local knowledge base indexed from your files in read-only mode
- Incremental file discovery with metadata coverage, pending batches, and status reporting
- Separate local web library for external sources, freshness, and background research cycles
- Operator-style planning with context panel and next-step visibility
- Persistent tasks with a local SQLite scheduler and `launchd` integration
- Personal macOS connectors for Calendar, Reminders, Notes, Contacts, and Mail
- Google Workspace connectors for Gmail, Google Calendar, and Drive
- Managed browser automation for navigation, extraction, screenshots, and supervised form work
- Persistent runtime profiles (`general`, `work`, `personal`, `research`, `coding`)
- Dedicated Markdown/Obsidian vault search tied to the active profile
- Session cost ledger and local JSON logs
- Auto mode with confirmation before enabling
- Optional PII redaction before cloud LLM calls
- Automatic local-only handling for turns that touch private Mac context
- `adv-archon daily` proactive routine
- Voice output with macOS `say`
- Local dictation with `faster-whisper`
- Optional wake-word startup flow with `--listen`
- Install and uninstall scripts for a global `adv-archon` command

## Quick start

1. Install dependencies with `uv sync --dev`
2. Copy `.env.example` values into `~/.adv-archon/.env`
3. Install Playwright's Chromium once with `uv run playwright install chromium`
4. Run `uv run adv-archon`

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

Task scheduler utilities:

```bash
adv-archon tasks
adv-archon tasks run-due
adv-archon knowledge status
adv-archon research status
```

## Current slash commands

- `/help`
- `/exit`
- `/mode <cloud|local>`
- `/profile [name|status]`
- `/read <path>`
- `/web <query>`
- `/vault <query>`
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
force_local_private_context = true
```

When enabled, ADV ARCHON replaces emails, phones, IBANs, and Spanish DNI/NIE identifiers with placeholders before sending cloud prompts, then restores them in the answer.

When `force_local_private_context` is enabled, turns that touch private Mac context such as local files, memory, notes, calendar, tasks, Gmail, Google Calendar, or Drive are resolved locally instead of going to the cloud model.

## Local knowledge and read-only learning

ADV ARCHON can learn about your work and preferences by indexing your local files into a private knowledge base under `~/.adv-archon/knowledge.db`.

By default it now treats your home directory as the primary read-only knowledge space and uses that context automatically when relevant.

It does not gain write access from that. File modifications still require explicit confirmation through the existing shell safety policy.

It now also keeps a metadata map of discovered files, so unsupported or oversized files can still exist in the knowledge graph as visible Mac context even if their full content was not embedded.

You can tune the knowledge scope in `~/.adv-archon/config.toml`:

```toml
[knowledge]
default_roots = ["~"]
vault_roots = ["~/Obsidian", "~/Documents/Notes"]
auto_index_on_search = true
max_files_per_root = 2000
max_file_bytes = 2000000
search_limit = 5
background_batch_size = 250
background_interval_minutes = 60

[profiles]
default = "general"

[profiles.work]
description = "Clientes, propuestas y repos de trabajo"
knowledge_roots = ["~/Desktop", "~/Documents"]
vault_roots = ["~/Obsidian/Work"]

[ui]
show_context_panel = true
operator_max_tool_steps = 8
```

## Profiles and Markdown vaults

ADV ARCHON can keep an active profile between launches:

```text
/profile status
/profile work
/profile research
```

The active profile affects:

- the context shown to the agent
- the default read-only knowledge roots
- the Markdown or Obsidian vault roots used by `/vault` and natural-language vault searches

Examples:

```text
busca en mi vault de obsidian todo lo relacionado con acme
```

```text
/vault propuesta acme
```

Maintenance commands:

```bash
adv-archon knowledge status
adv-archon knowledge run-batch
adv-archon knowledge search "atomic habits"
adv-archon knowledge install-agent
```

## Personal assistant connectors

ADV ARCHON can now use native macOS apps in supervised mode:

- Calendar: upcoming events
- Reminders: list and create reminders
- Notes: search contents and create notes after confirmation
- Contacts: search people by name, email, or phone
- Mail: draft emails after confirmation

Useful natural-language prompts:

```text
que tengo esta semana en el calendario
```

```text
crea un recordatorio para llamar a ACME mañana a las 9
```

```text
busca en mis notas todo lo relacionado con propuesta acme
```

```text
hazme una nota sobre ~/Desktop/Libros/atomic-habits.pdf
```

```text
crea una nota titulada Ideas ADV que diga revisar Gmail y Drive
```

```text
prepara un borrador de correo para este cliente con seguimiento de la propuesta
```

macOS may ask your terminal for access to Calendar, Reminders, Notes, Contacts, or Mail the first time.

## Google Workspace connectors

ADV ARCHON can also use Google Workspace in supervised mode:

- Gmail: search and read threads, plus draft creation with confirmation
- Google Calendar: list events and create events with confirmation
- Google Drive: search files and read supported text content

Setup:

1. Create a Google OAuth desktop client in Google Cloud.
2. Save the JSON credentials file at:

```text
~/.adv-archon/google-client-secret.json
```

3. On first real use, ADV ARCHON will open the local OAuth flow in the browser and store the token at:

```text
~/.adv-archon/google-token.json
```

Example prompts:

```text
qué correos importantes tengo en gmail
```

```text
qué tengo mañana en google calendar
```

```text
busca en google drive la propuesta de acme
```

```text
crea un evento en google calendar para mañana a las 10 con acme
```

## Local web library and background research

ADV ARCHON can now keep a separate local library of external web sources in `~/.adv-archon/web-library.db`.

That web library is intentionally separate from the Mac knowledge base:

- your Mac files remain the primary private source of truth
- web sources are supporting context, perspective, and external reality checks
- everything saved from the web stays local on disk

Useful commands:

```bash
adv-archon research status
adv-archon research run-once "ai consulting spain" "llm agents market"
adv-archon research search "consultoria ia"
adv-archon research install-agent "ai consulting spain" "llm agents market"
```

Natural-language examples:

```text
guarda una búsqueda web sobre consultoría IA en españa
```

```text
busca en tu biblioteca web todo lo relacionado con agentes
```

## Browser automation

ADV ARCHON can keep a managed browser session and use it through natural language. Navigation and extraction are unattended; clicks, fills, and similar state-changing actions stay behind confirmation.

Examples:

```text
abre la web de openai y saca una captura de la portada
```

```text
navega a esta pagina, extrae el texto principal y resumelo
```

```text
abre este formulario y rellena los campos, pero no envíes nada sin avisarme
```

Playwright stores its browser profile under `~/.adv-archon/browser-profile/`.

## Persistent tasks

ADV ARCHON can save private scheduled tasks in `~/.adv-archon/tasks.db` and trigger them with `launchd`.

Examples:

```text
recuérdame mañana a las 9 que envíe la propuesta a ACME
```

```text
crea una tarea recurrente todos los lunes para revisar leads
```

```text
qué tareas persistentes tengo pendientes
```

To enable background task checks, ask ADV ARCHON naturally to install the scheduler, or use the task tool from the REPL and confirm when prompted.

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
