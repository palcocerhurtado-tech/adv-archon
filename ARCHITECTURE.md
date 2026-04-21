# Architecture

## Overview

ADV ARCHON is a lightweight terminal-native agent with a small internal dispatcher instead of a heavyweight orchestration framework.

## Main components

- `main.py`: CLI entrypoint and process bootstrap
- `core/config.py`: user config and private path management
- `core/context.py`: local runtime awareness for cwd, git, time, and project cues
- `core/llm.py`: single interface for Gemini and Ollama
- `core/memory.py`: SQLite-backed long-term memory with local embeddings
- `core/intent.py`: lightweight intent router for natural-language requests
- `core/knowledge.py`: read-only local knowledge index across personal files
- `core/tasks.py`: persistent scheduled tasks and local `launchd` scheduler support
- `core/costs.py`: in-session token and cost accounting
- `core/logging.py`: local JSON session event logging
- `core/privacy.py`: optional placeholder-based PII redaction for cloud LLM calls
- `core/daily.py`: proactive daily summary routine from context, logs, memory, and git state
- `core/agent.py`: agent loop, planner step, and tool dispatch
- `core/session.py`: in-memory and persisted session history
- `tools/files.py`: local document readers with OCR fallback
- `tools/task_tools.py`: persistent task creation, listing, completion, cancellation, and scheduler install
- `tools/personal.py`: macOS connectors for Calendar, Reminders, Notes, Contacts, and Mail
- `tools/browser.py`: managed Playwright session for browser automation
- `tools/shell.py`: shell execution policy, whitelist, blacklist, and auto mode
- `tools/python_sandbox.py`: ephemeral Python snippet execution
- `tools/mac.py`: clipboard and `open` integration for macOS
- `voice/tts.py`: non-blocking speech output through macOS `say`
- `voice/stt.py`: local microphone capture and Whisper transcription
- `ui/`: terminal rendering, REPL, and slash commands

## Agent flow

1. Load system prompt and runtime context
2. Ask the planner model whether to answer directly or call a tool
3. Inject runtime context and relevant long-term memories into the turn
4. Auto-search the local knowledge base when the request looks document- or assistant-heavy
5. Execute tools transparently, including multi-step operator flows
6. Feed tool results back into the conversation
7. Stream the final user-facing answer and record usage/log events

## Intent and operator flow

The upgraded agent now does four things before replying:

1. Classifies the request into intent categories such as chat, coding, documents, web, shell, or personal assistant.
2. Pulls structured memory relevant to that request.
3. Searches the local knowledge base when the prompt suggests personal files or background context would help.
4. Chooses direct mode or operator mode, where it advances one tool step at a time and exposes the next step in a context panel.

## Phase 2 assistant surface

Phase 2 expands the assistant in three directions:

1. `Persistent tasks`: reminders and recurring tasks live in `tasks.db`, can be queried in natural language, and can fire via `launchd`.
2. `Personal connectors`: ADV ARCHON can inspect Calendar, Reminders, Notes, Contacts, and create Mail drafts, always keeping user-visible confirmation for state-changing actions.
3. `Browser automation`: a managed Playwright session allows supervised browsing, text extraction, screenshots, and guided form interaction.

## Command execution policy

- Safe read-only commands may run immediately.
- Non-whitelisted shell commands require user confirmation.
- Auto mode disables those prompts only after a separate session-level confirmation.
- High-risk commands remain guarded even in auto mode.

## Personal connector safety

- Read-only connectors such as Calendar, Notes, Contacts, and reminder listing run directly.
- Writes such as creating reminders, drafting emails, or installing the task scheduler require confirmation.
- Browser navigation and extraction are low-risk; browser clicks and fills remain supervised.

## PII redaction flow

When cloud redaction is enabled:

1. ADV ARCHON detects supported PII in outgoing prompts.
2. Matching values are replaced with stable placeholders.
3. The redacted prompt is sent to Gemini.
4. Placeholders are restored in the returned assistant text.

## Voice flow

1. The REPL streams assistant text to the terminal.
2. If voice is enabled, ADV ARCHON sends the final response to `say` in a background subprocess.
3. `Ctrl+C` stops active speech without killing the whole REPL.
4. `/listen` records a microphone turn, transcribes it locally, and injects the text as the next user prompt.
5. `--listen` does the same at startup, optionally gated by a wake-word when configured.

## Scheduler flow

1. The user creates a persistent task in natural language.
2. ADV ARCHON stores it in `~/.adv-archon/tasks.db`.
3. If the user enables background checks, ADV ARCHON installs a `launchd` plist.
4. `launchd` periodically runs `adv-archon tasks run-due`.
5. Due tasks trigger local macOS notifications and are either rescheduled or left marked as due.

## Why a custom dispatcher

Block 1 keeps the control surface small:

- fewer dependencies
- predictable tool schema
- easy auditing of every tool call
- simpler debugging for a local personal assistant
