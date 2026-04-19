# Architecture

## Overview

ADV ARCHON is a lightweight terminal-native agent with a small internal dispatcher instead of a heavyweight orchestration framework.

## Main components

- `main.py`: CLI entrypoint and process bootstrap
- `core/config.py`: user config and private path management
- `core/context.py`: local runtime awareness for cwd, git, time, and project cues
- `core/llm.py`: single interface for Gemini and Ollama
- `core/memory.py`: SQLite-backed long-term memory with local embeddings
- `core/costs.py`: in-session token and cost accounting
- `core/logging.py`: local JSON session event logging
- `core/privacy.py`: optional placeholder-based PII redaction for cloud LLM calls
- `core/daily.py`: proactive daily summary routine from context, logs, memory, and git state
- `core/agent.py`: agent loop, planner step, and tool dispatch
- `core/session.py`: in-memory and persisted session history
- `tools/files.py`: local document readers with OCR fallback
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
4. Execute tools transparently
5. Feed tool results back into the conversation
6. Stream the final user-facing answer and record usage/log events

## Command execution policy

- Safe read-only commands may run immediately.
- Non-whitelisted shell commands require user confirmation.
- Auto mode disables those prompts only after a separate session-level confirmation.
- High-risk commands remain guarded even in auto mode.

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

## Why a custom dispatcher

Block 1 keeps the control surface small:

- fewer dependencies
- predictable tool schema
- easy auditing of every tool call
- simpler debugging for a local personal assistant
