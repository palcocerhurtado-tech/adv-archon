from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from adv_archon.core.profiles import ProfileDefinition

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
    evals_db: Path = field(init=False)
    knowledge_db: Path = field(init=False)
    web_library_db: Path = field(init=False)
    tasks_db: Path = field(init=False)
    benchmark_cases_file: Path = field(init=False)
    browser_profile_dir: Path = field(init=False)
    profile_state_file: Path = field(init=False)
    google_client_secret_file: Path = field(init=False)
    google_token_file: Path = field(init=False)
    sessions_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.config_file = self.root / "config.toml"
        self.env_file = self.root / ".env"
        self.history_file = self.root / "history.txt"
        self.memory_db = self.root / "memory.db"
        self.evals_db = self.root / "evals.db"
        self.knowledge_db = self.root / "knowledge.db"
        self.web_library_db = self.root / "web-library.db"
        self.tasks_db = self.root / "tasks.db"
        self.benchmark_cases_file = self.root / "benchmark-cases.json"
        self.browser_profile_dir = self.root / "browser-profile"
        self.profile_state_file = self.root / "active-profile.txt"
        self.google_client_secret_file = self.root / "google-client-secret.json"
        self.google_token_file = self.root / "google-token.json"
        self.sessions_dir = self.root / "sessions"
        self.logs_dir = self.root / "logs"


@dataclass(slots=True)
class LLMConfig:
    mode: str = "cloud"
    gemini_model: str = "gemini-2.5-flash"
    ollama_model: str = "llama3.1:8b"
    fast_local_model: str | None = None
    planner_local_model: str | None = None
    document_local_model: str | None = None
    coding_local_model: str | None = None
    reasoning_local_model: str | None = None
    fast_cloud_model: str | None = None
    planner_cloud_model: str | None = None
    document_cloud_model: str | None = None
    coding_cloud_model: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: int = 180
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = "-1"
    gemini_api_key: str | None = None
    temperature: float = 0.2
    redact_cloud_pii: bool = False
    force_local_private_context: bool = True
    task_routing_enabled: bool = True
    tool_call_repair: bool = True


@dataclass(slots=True)
class UIConfig:
    show_tool_input: bool = False
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
    vault_roots: tuple[str, ...] = ()
    auto_index_on_search: bool = True
    max_files_per_root: int = 2000
    max_file_bytes: int = 2_000_000
    search_limit: int = 5
    background_batch_size: int = 250
    background_interval_minutes: int = 60


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
    rate_limit_interval_seconds: float = 0.2
    retry_attempts: int = 2
    retry_base_delay_seconds: float = 0.6
    max_concurrency: int = 1


@dataclass(slots=True)
class WebConfig:
    rate_limit_interval_seconds: float = 0.2
    retry_attempts: int = 3
    retry_base_delay_seconds: float = 0.6
    max_concurrency: int = 2


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
class GoogleConfig:
    enabled: bool = True
    client_secret_file: Path = field(
        default_factory=lambda: Path.home() / ".adv-archon" / "google-client-secret.json"
    )
    token_file: Path = field(
        default_factory=lambda: Path.home() / ".adv-archon" / "google-token.json"
    )
    default_calendar_id: str = "primary"
    gmail_default_max_results: int = 10
    drive_default_max_results: int = 10
    rate_limit_interval_seconds: float = 0.25
    retry_attempts: int = 3
    retry_base_delay_seconds: float = 0.8
    max_concurrency: int = 2


@dataclass(slots=True)
class FileAccessConfig:
    allowed_roots: tuple[str, ...] = ("~",)
    sensitive_roots: tuple[str, ...] = (
        "/System",
        "/Library",
        "/Applications",
        "/private",
        "/usr",
    )
    allow_sensitive_reads: bool = False


@dataclass(slots=True)
class ResearchConfig:
    enabled: bool = True
    seed_queries: tuple[str, ...] = ()
    search_results_per_query: int = 5
    fetch_top_results: int = 2
    launch_agent_interval_minutes: int = 180


@dataclass(slots=True)
class BenchmarkConfig:
    default_suite: str = "archon-internal"
    default_benchmark: str = "real-cases"
    max_cases: int = 12


@dataclass(slots=True)
class ProfilesConfig:
    default_profile: str = "general"
    definitions: dict[str, ProfileDefinition] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    paths: PathsConfig
    llm: LLMConfig
    ui: UIConfig
    memory: MemoryConfig
    knowledge: KnowledgeConfig
    files: FileAccessConfig
    shell: ShellConfig
    tasks: TasksConfig
    browser: BrowserConfig
    web: WebConfig
    voice: VoiceConfig
    google: GoogleConfig
    research: ResearchConfig
    benchmark: BenchmarkConfig
    profiles: ProfilesConfig
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
        fast_local_model=str(_lookup(data, "llm", "fast_local_model", default="")).strip()
        or None,
        planner_local_model=str(
            _lookup(data, "llm", "planner_local_model", default="")
        ).strip()
        or None,
        document_local_model=str(
            _lookup(data, "llm", "document_local_model", default="")
        ).strip()
        or None,
        coding_local_model=str(
            _lookup(data, "llm", "coding_local_model", default="")
        ).strip()
        or None,
        reasoning_local_model=str(
            _lookup(data, "llm", "reasoning_local_model", default="")
        ).strip()
        or None,
        fast_cloud_model=str(_lookup(data, "llm", "fast_cloud_model", default="")).strip()
        or None,
        planner_cloud_model=str(
            _lookup(data, "llm", "planner_cloud_model", default="")
        ).strip()
        or None,
        document_cloud_model=str(
            _lookup(data, "llm", "document_cloud_model", default="")
        ).strip()
        or None,
        coding_cloud_model=str(
            _lookup(data, "llm", "coding_cloud_model", default="")
        ).strip()
        or None,
        ollama_base_url=os.getenv("ADV_ARCHON_OLLAMA_BASE_URL")
        or _lookup(data, "llm", "ollama_base_url", default="http://127.0.0.1:11434"),
        ollama_timeout_seconds=int(
            os.getenv("ADV_ARCHON_OLLAMA_TIMEOUT_SECONDS")
            or _lookup(data, "llm", "ollama_timeout_seconds", default=180)
        ),
        ollama_num_ctx=int(_lookup(data, "llm", "ollama_num_ctx", default=8192)),
        ollama_keep_alive=str(_lookup(data, "llm", "ollama_keep_alive", default="-1")),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        temperature=float(_lookup(data, "llm", "temperature", default=0.2)),
        redact_cloud_pii=bool(_lookup(data, "privacy", "redact_cloud_pii", default=False)),
        force_local_private_context=bool(
            _lookup(data, "privacy", "force_local_private_context", default=True)
        ),
        task_routing_enabled=bool(
            _lookup(data, "llm", "task_routing_enabled", default=True)
        ),
        tool_call_repair=bool(_lookup(data, "llm", "tool_call_repair", default=True)),
    )

    ui = UIConfig(
        show_tool_input=bool(_lookup(data, "ui", "show_tool_input", default=False)),
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
    vault_roots = _lookup(
        data,
        "knowledge",
        "vault_roots",
        default=[],
    )
    if not isinstance(vault_roots, list):
        vault_roots = []
    knowledge = KnowledgeConfig(
        default_roots=tuple(str(item) for item in default_roots),
        vault_roots=tuple(str(item) for item in vault_roots),
        auto_index_on_search=bool(
            _lookup(data, "knowledge", "auto_index_on_search", default=True)
        ),
        max_files_per_root=int(
            _lookup(data, "knowledge", "max_files_per_root", default=2000)
        ),
        max_file_bytes=int(_lookup(data, "knowledge", "max_file_bytes", default=2_000_000)),
        search_limit=int(_lookup(data, "knowledge", "search_limit", default=5)),
        background_batch_size=int(
            _lookup(data, "knowledge", "background_batch_size", default=250)
        ),
        background_interval_minutes=int(
            _lookup(data, "knowledge", "background_interval_minutes", default=60)
        ),
    )
    raw_allowed_roots = _lookup(data, "files", "allowed_roots", default=["~"])
    if not isinstance(raw_allowed_roots, list):
        raw_allowed_roots = ["~"]
    raw_sensitive_roots = _lookup(
        data,
        "files",
        "sensitive_roots",
        default=["/System", "/Library", "/Applications", "/private", "/usr"],
    )
    if not isinstance(raw_sensitive_roots, list):
        raw_sensitive_roots = ["/System", "/Library", "/Applications", "/private", "/usr"]
    files = FileAccessConfig(
        allowed_roots=tuple(str(item) for item in raw_allowed_roots),
        sensitive_roots=tuple(str(item) for item in raw_sensitive_roots),
        allow_sensitive_reads=bool(
            _lookup(data, "files", "allow_sensitive_reads", default=False)
        ),
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
        rate_limit_interval_seconds=float(
            _lookup(data, "browser", "rate_limit_interval_seconds", default=0.2)
        ),
        retry_attempts=int(_lookup(data, "browser", "retry_attempts", default=2)),
        retry_base_delay_seconds=float(
            _lookup(data, "browser", "retry_base_delay_seconds", default=0.6)
        ),
        max_concurrency=int(_lookup(data, "browser", "max_concurrency", default=1)),
    )
    web = WebConfig(
        rate_limit_interval_seconds=float(
            _lookup(data, "web", "rate_limit_interval_seconds", default=0.2)
        ),
        retry_attempts=int(_lookup(data, "web", "retry_attempts", default=3)),
        retry_base_delay_seconds=float(
            _lookup(data, "web", "retry_base_delay_seconds", default=0.6)
        ),
        max_concurrency=int(_lookup(data, "web", "max_concurrency", default=2)),
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
    google = GoogleConfig(
        enabled=bool(_lookup(data, "google", "enabled", default=True)),
        client_secret_file=Path(
            os.getenv("GOOGLE_CLIENT_SECRET_FILE")
            or _lookup(
                data,
                "google",
                "client_secret_file",
                default=str(paths.google_client_secret_file),
            )
        ).expanduser(),
        token_file=Path(
            os.getenv("GOOGLE_TOKEN_FILE")
            or _lookup(
                data,
                "google",
                "token_file",
                default=str(paths.google_token_file),
            )
        ).expanduser(),
        default_calendar_id=str(
            _lookup(data, "google", "default_calendar_id", default="primary")
        ),
        gmail_default_max_results=int(
            _lookup(data, "google", "gmail_default_max_results", default=10)
        ),
        drive_default_max_results=int(
            _lookup(data, "google", "drive_default_max_results", default=10)
        ),
        rate_limit_interval_seconds=float(
            _lookup(data, "google", "rate_limit_interval_seconds", default=0.25)
        ),
        retry_attempts=int(_lookup(data, "google", "retry_attempts", default=3)),
        retry_base_delay_seconds=float(
            _lookup(data, "google", "retry_base_delay_seconds", default=0.8)
        ),
        max_concurrency=int(_lookup(data, "google", "max_concurrency", default=2)),
    )
    seed_queries = _lookup(data, "research", "seed_queries", default=[])
    if not isinstance(seed_queries, list):
        seed_queries = []
    research = ResearchConfig(
        enabled=bool(_lookup(data, "research", "enabled", default=True)),
        seed_queries=tuple(str(item) for item in seed_queries),
        search_results_per_query=int(
            _lookup(data, "research", "search_results_per_query", default=5)
        ),
        fetch_top_results=int(_lookup(data, "research", "fetch_top_results", default=2)),
        launch_agent_interval_minutes=int(
            _lookup(data, "research", "launch_agent_interval_minutes", default=180)
        ),
    )
    benchmark = BenchmarkConfig(
        default_suite=str(
            _lookup(data, "benchmark", "default_suite", default="archon-internal")
        ),
        default_benchmark=str(
            _lookup(data, "benchmark", "default_benchmark", default="real-cases")
        ),
        max_cases=int(_lookup(data, "benchmark", "max_cases", default=12)),
    )
    profiles_data = _lookup(data, "profiles", default={})
    if not isinstance(profiles_data, dict):
        profiles_data = {}
    definitions: dict[str, ProfileDefinition] = {}
    for profile_name, raw_entry in profiles_data.items():
        if profile_name == "default" or not isinstance(raw_entry, dict):
            continue
        raw_knowledge_roots = raw_entry.get("knowledge_roots", [])
        if not isinstance(raw_knowledge_roots, list):
            raw_knowledge_roots = []
        raw_vault_roots = raw_entry.get("vault_roots", [])
        if not isinstance(raw_vault_roots, list):
            raw_vault_roots = []
        definitions[profile_name] = ProfileDefinition(
            name=profile_name,
            description=str(raw_entry.get("description", "")).strip()
            or f"Perfil {profile_name}.",
            system_hint=str(raw_entry.get("system_hint", "")).strip()
            or f"Prioritize the {profile_name} profile.",
            knowledge_roots=tuple(str(item) for item in raw_knowledge_roots),
            vault_roots=tuple(str(item) for item in raw_vault_roots),
        )
    profiles = ProfilesConfig(
        default_profile=str(profiles_data.get("default", "general")),
        definitions=definitions,
    )

    system_prompt_path = system_prompt_override or DEFAULT_SYSTEM_PROMPT

    return AppConfig(
        paths=paths,
        llm=llm,
        ui=ui,
        memory=memory,
        knowledge=knowledge,
        files=files,
        shell=shell,
        tasks=tasks,
        browser=browser,
        web=web,
        voice=voice,
        google=google,
        research=research,
        benchmark=benchmark,
        profiles=profiles,
        system_prompt_path=system_prompt_path,
    )
