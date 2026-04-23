# Setup

## Requirements

- macOS
- Python 3.11+
- `uv`
- Optional: Ollama running locally
- Optional: `portaudio` if microphone capture needs it on your Mac

## Recommended installation

From the repository root:

```bash
uv sync --dev
uv run playwright install chromium
./scripts/install.sh
```

This installs the global `adv-archon` command using `uv tool install`.

The package also exposes the short alias:

```bash
adv
```

## User config directory

ADV ARCHON stores private config under:

```text
~/.adv-archon/
```

At first run it creates:

- `config.toml`
- `.env`
- `history.txt`
- `sessions/`
- `logs/`

The directory is created with `0700` permissions.

## Optional config

You can create `~/.adv-archon/config.toml` to override runtime defaults.

Example:

```toml
[privacy]
redact_cloud_pii = true
force_local_private_context = true

[shell]
timeout_seconds = 20

[shell.whitelist]
commands = ["ls", "pwd", "cat", "rg", "git", "date"]

[voice]
enabled = false
say_voice = "Jorge"
rate_wpm = 190
stt_model = "small"
stt_language = "es"
wake_word_enabled = false
wake_word_keyword = "jarvis"

[knowledge]
default_roots = ["~"]
auto_index_on_search = true
max_files_per_root = 2000
max_file_bytes = 2000000
search_limit = 5
background_batch_size = 250
background_interval_minutes = 60

[google]
enabled = true
client_secret_file = "~/.adv-archon/google-client-secret.json"
token_file = "~/.adv-archon/google-token.json"
default_calendar_id = "primary"
gmail_default_max_results = 10
drive_default_max_results = 10

[research]
enabled = true
seed_queries = ["ai consulting spain", "llm agents market"]
search_results_per_query = 5
fetch_top_results = 2
launch_agent_interval_minutes = 180

[ui]
show_context_panel = true
operator_max_tool_steps = 8

[tasks]
notifications_enabled = true
launch_agent_interval_minutes = 30
default_timezone = "Europe/Madrid"

[browser]
enabled = true
headless = true
browser_name = "chromium"
default_timeout_ms = 10000
```

## Minimal `.env`

```dotenv
GEMINI_API_KEY=your_key_here
ADV_ARCHON_DEFAULT_MODE=cloud
ADV_ARCHON_DEFAULT_GEMINI_MODEL=gemini-2.5-flash
ADV_ARCHON_DEFAULT_OLLAMA_MODEL=llama3.1:8b
ADV_ARCHON_OLLAMA_BASE_URL=http://127.0.0.1:11434
PORCUPINE_ACCESS_KEY=
```

## Embeddings

Long-term memory uses `sentence-transformers` with the `all-MiniLM-L6-v2` model.

The first memory operation may download the model once into the local cache if it is not present yet.

## Document support and OCR

Block 3 adds structured readers for:

- PDF
- DOCX
- XLSX
- PPTX
- HTML

OCR uses `pytesseract`.

Recommended system packages:

```bash
brew install tesseract poppler
```

- `tesseract` is needed for image OCR.
- `poppler` is needed for scanned PDF OCR fallback through `pdf2image`.

## Voice and dictation

Block 5 adds:

- TTS with macOS `say`
- `/voice on|off|status`
- `/listen` for one-shot dictation inside the REPL
- `adv-archon --listen` for a startup spoken prompt

Whisper runs locally through `faster-whisper`.

If microphone capture fails because PortAudio is missing, install:

```bash
brew install portaudio
```

Wake-word support is optional and uses `pvporcupine` plus `PORCUPINE_ACCESS_KEY`.

## Personal connectors

Phase 2 adds native macOS connectors for:

- Calendar
- Reminders
- Notes
- Contacts
- Mail

The first real use may trigger macOS permission prompts for your terminal app.

## Google Workspace connectors

To enable Gmail, Google Calendar, and Drive:

1. Create a Google OAuth desktop client in Google Cloud.
2. Save the downloaded JSON in:

```text
~/.adv-archon/google-client-secret.json
```

3. On first use, ADV ARCHON will open a local OAuth flow and persist the token in:

```text
~/.adv-archon/google-token.json
```

The default scopes cover:

- Gmail read and draft creation
- Google Calendar read and event creation
- Google Drive read-only search and file access

## Browser automation

Browser automation uses Playwright with a persistent local profile at:

```text
~/.adv-archon/browser-profile/
```

Install the browser runtime once:

```bash
uv run playwright install chromium
```

Navigation and extraction can run directly; state-changing actions such as clicks and form fills are still confirmed interactively.

## Persistent tasks

Persistent reminders and scheduled tasks are stored in:

```text
~/.adv-archon/tasks.db
```

ADV ARCHON can also install a `launchd` job in:

```text
~/Library/LaunchAgents/com.adv-archon.tasks.plist
```

That scheduler runs `adv-archon tasks run-due` on a recurring interval and shows macOS notifications for due tasks.

## Read-only file learning

ADV ARCHON can index your files as personal context without turning that into write access.

Default behavior:

- read access is broad across your configured knowledge roots
- that includes your Desktop and its folders when they sit under configured roots such as `~`
- knowledge retrieval is automatic when the request looks document-heavy or assistant-like
- discovery keeps metadata for files even when full content cannot be embedded
- writes still stay behind confirmation gates
- writing a note in macOS Notes also stays behind explicit confirmation

Useful maintenance commands:

```bash
adv-archon knowledge status
adv-archon knowledge run-batch
adv-archon knowledge install-agent
```

The optional background indexer uses:

```text
~/Library/LaunchAgents/com.adv-archon.knowledge.plist
```

## Background web research

ADV ARCHON can also maintain a separate local web library under:

```text
~/.adv-archon/web-library.db
```

This store is intended for external perspective only. Your Mac knowledge base remains primary.

Useful commands:

```bash
adv-archon research status
adv-archon research run-once
adv-archon research search "query"
adv-archon research install-agent
```

The optional background research agent uses:

```text
~/Library/LaunchAgents/com.adv-archon.research.plist
```

For broader access on macOS protected folders, you may need to grant Full Disk Access to the terminal app you use.

## Fallback without `uv`

If `uv` is unavailable, create a venv manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

Then run:

```bash
adv-archon
```
