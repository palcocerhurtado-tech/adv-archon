from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_SYSTEM_PROMPT = PACKAGE_ROOT / "resources" / "system.md"
DEFAULT_SHELL_WHITELIST = (
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "wc",
    "file",
    "stat",
    "which",
    "type",
    "grep",
    "rg",
    "find",
    "tree",
    "echo",
    "date",
    "uname",
    "whoami",
    "hostname",
)


def _discover_project_root() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "prompts" / "system.md"
        if candidate.exists():
            return parent
    return None


PROJECT_ROOT = _discover_project_root()
DEFAULT_SYSTEM_PROMPT = (
    PROJECT_ROOT / "prompts" / "system.md"
    if PROJECT_ROOT is not None
    else BUNDLED_SYSTEM_PROMPT
)


def _default_user_root() -> Path:
    override = os.getenv("ADV_ARCHON_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".adv-archon"


@dataclass(slots=True)
class PathsConfig:
    root: Path = field(default_factory=_default_user_root)
    config_file: Path = field(init=False)
    env_file: Path = field(init=False)
    history_file: Path = field(init=False)
    memory_db: Path = field(init=False)
    knowledge_db: Path = field(init=False)
    tasks_db: Path = field(init=False)
    browser_profile_dir: Path = field(init=False)
    sessions_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.config_file = self.root / "config.toml"
        self.env_file = self.root / ".env"
        self.history_file = self.root / "history.txt"
        self.memory_db = self.root / "memory.db"
        self.knowledge_db = self.root / "knowledge.db"
        self.tasks_db = self.root / "tasks.db"
        self.browser_profile_dir = self.root / "browser-profile"
        self.sessions_dir = self.root / "sessions"
        self.logs_dir = self.root / "logs"


@dataclass(slots=True)
class LLMConfig:
    mode: str = "cloud"
    gemini_model: str = "gemini-2.5-flash"
    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    gemini_api_key: str | None = None
    temperature: float = 0.2
    redact_cloud_pii: bool = False


@dataclass(slots=True)
class UIConfig:
    show_tool_input: bool = True
    max_tool_steps: int = 4
    operator_max_tool_steps: int = 8
    show_context_panel: bool = True


@dataclass(slots=True)
class MemoryConfig:
    embedding_model: str = "all-MiniLM-L6-v2"
    auto_recall_limit: int = 3
    slash_recall_limit: int = 5


@dataclass(slots=True)
class KnowledgeConfig:
    default_roots: tuple[str, ...] = ("~",)
    auto_index_on_search: bool = True
    max_files_per_root: int = 2000
    max_file_bytes: int = 2_000_000
    search_limit: int = 5


@dataclass(slots=True)
class ShellConfig:
    timeout_seconds: int = 20
    whitelist_commands: tuple[str, ...] = DEFAULT_SHELL_WHITELIST


@dataclass(slots=True)
class TasksConfig:
    notifications_enabled: bool = True
    launch_agent_interval_minutes: int = 30
    default_timezone: str = "Europe/Madrid"


@dataclass(slots=True)
class BrowserConfig:
    enabled: bool = True
    headless: bool = True
    browser_name: str = "chromium"
    default_timeout_ms: int = 10000


@dataclass(slots=True)
class VoiceConfig:
    enabled: bool = False
    say_voice: str = "Jorge"
    rate_wpm: int = 190
    stt_model: str = "small"
    stt_language: str = "es"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    sample_rate: int = 16000
    max_record_seconds: int = 45
    silence_seconds: float = 1.2
    silence_threshold: float = 0.015
    wake_word_enabled: bool = False
    wake_word_keyword: str = "jarvis"
    wake_word_timeout_seconds: int = 60
    porcupine_access_key: str | None = None


@dataclass(slots=True)
class AppConfig:
    paths: PathsConfig
    llm: LLMConfig
    ui: UIConfig
    memory: MemoryConfig
    knowledge: KnowledgeConfig
    shell: ShellConfig
    tasks: TasksConfig
    browser: BrowserConfig
    voice: VoiceConfig
    system_prompt_path: Path


def _ensure_private_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for child in (root, root / "sessions", root / "logs"):
        child.mkdir(parents=True, exist_ok=True)
        os.chmod(child, stat.S_IRWXU)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _lookup(data: dict[str, Any], *keys: str, default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def load_app_config(
    *,
    mode_override: str | None = None,
    system_prompt_override: Path | None = None,
) -> AppConfig:
    paths = PathsConfig()
    _ensure_private_root(paths.root)
    load_dotenv(paths.env_file, override=False)

    data = _load_toml(paths.config_file)

    llm = LLMConfig(
        mode=mode_override
        or os.getenv("ADV_ARCHON_DEFAULT_MODE")
        or _lookup(data, "llm", "mode", default="cloud"),
        gemini_model=os.getenv("ADV_ARCHON_DEFAULT_GEMINI_MODEL")
        or _lookup(data, "llm", "gemini_model", default="gemini-2.5-flash"),
        ollama_model=os.getenv("ADV_ARCHON_DEFAULT_OLLAMA_MODEL")
        or _lookup(data, "llm", "ollama_model", default="llama3.1:8b"),
        ollama_base_url=os.getenv("ADV_ARCHON_OLLAMA_BASE_URL")
        or _lookup(data, "llm", "ollama_base_url", default="http://127.0.0.1:11434"),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        temperature=float(_lookup(data, "llm", "temperature", default=0.2)),
        redact_cloud_pii=bool(_lookup(data, "privacy", "redact_cloud_pii", default=False)),
    )

    ui = UIConfig(
        show_tool_input=bool(_lookup(data, "ui", "show_tool_input", default=True)),
        max_tool_steps=int(_lookup(data, "ui", "max_tool_steps", default=4)),
        operator_max_tool_steps=int(
            _lookup(data, "ui", "operator_max_tool_steps", default=8)
        ),
        show_context_panel=bool(_lookup(data, "ui", "show_context_panel", default=True)),
    )

    memory = MemoryConfig(
        embedding_model=str(
            _lookup(data, "memory", "embedding_model", default="all-MiniLM-L6-v2")
        ),
        auto_recall_limit=int(_lookup(data, "memory", "auto_recall_limit", default=3)),
        slash_recall_limit=int(_lookup(data, "memory", "slash_recall_limit", default=5)),
    )
    default_roots = _lookup(
        data,
        "knowledge",
        "default_roots",
        default=["~"],
    )
    if not isinstance(default_roots, list):
        default_roots = ["~"]
    knowledge = KnowledgeConfig(
        default_roots=tuple(str(item) for item in default_roots),
        auto_index_on_search=bool(
            _lookup(data, "knowledge", "auto_index_on_search", default=True)
        ),
        max_files_per_root=int(
            _lookup(data, "knowledge", "max_files_per_root", default=2000)
        ),
        max_file_bytes=int(_lookup(data, "knowledge", "max_file_bytes", default=2_000_000)),
        search_limit=int(_lookup(data, "knowledge", "search_limit", default=5)),
    )
    whitelist = _lookup(
        data,
        "shell",
        "whitelist",
        "commands",
        default=list(DEFAULT_SHELL_WHITELIST),
    )
    if not isinstance(whitelist, list):
        whitelist = list(DEFAULT_SHELL_WHITELIST)
    shell = ShellConfig(
        timeout_seconds=int(_lookup(data, "shell", "timeout_seconds", default=20)),
        whitelist_commands=tuple(str(item) for item in whitelist),
    )
    tasks = TasksConfig(
        notifications_enabled=bool(
            _lookup(data, "tasks", "notifications_enabled", default=True)
        ),
        launch_agent_interval_minutes=int(
            _lookup(data, "tasks", "launch_agent_interval_minutes", default=30)
        ),
        default_timezone=str(
            _lookup(data, "tasks", "default_timezone", default="Europe/Madrid")
        ),
    )
    browser = BrowserConfig(
        enabled=bool(_lookup(data, "browser", "enabled", default=True)),
        headless=bool(_lookup(data, "browser", "headless", default=True)),
        browser_name=str(_lookup(data, "browser", "browser_name", default="chromium")),
        default_timeout_ms=int(
            _lookup(data, "browser", "default_timeout_ms", default=10000)
        ),
    )
    voice = VoiceConfig(
        enabled=bool(_lookup(data, "voice", "enabled", default=False)),
        say_voice=str(_lookup(data, "voice", "say_voice", default="Jorge")),
        rate_wpm=int(_lookup(data, "voice", "rate_wpm", default=190)),
        stt_model=str(_lookup(data, "voice", "stt_model", default="small")),
        stt_language=str(_lookup(data, "voice", "stt_language", default="es")),
        stt_device=str(_lookup(data, "voice", "stt_device", default="cpu")),
        stt_compute_type=str(_lookup(data, "voice", "stt_compute_type", default="int8")),
        sample_rate=int(_lookup(data, "voice", "sample_rate", default=16000)),
        max_record_seconds=int(_lookup(data, "voice", "max_record_seconds", default=45)),
        silence_seconds=float(_lookup(data, "voice", "silence_seconds", default=1.2)),
        silence_threshold=float(_lookup(data, "voice", "silence_threshold", default=0.015)),
        wake_word_enabled=bool(_lookup(data, "voice", "wake_word_enabled", default=False)),
        wake_word_keyword=str(_lookup(data, "voice", "wake_word_keyword", default="jarvis")),
        wake_word_timeout_seconds=int(
            _lookup(data, "voice", "wake_word_timeout_seconds", default=60)
        ),
        porcupine_access_key=os.getenv("PORCUPINE_ACCESS_KEY")
        or _lookup(data, "voice", "porcupine_access_key", default=None),
    )

    system_prompt_path = system_prompt_override or DEFAULT_SYSTEM_PROMPT

    return AppConfig(
        paths=paths,
        llm=llm,
        ui=ui,
        memory=memory,
        knowledge=knowledge,
        shell=shell,
        tasks=tasks,
        browser=browser,
        voice=voice,
        system_prompt_path=system_prompt_path,
    )
