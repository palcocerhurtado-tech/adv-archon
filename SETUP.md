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
