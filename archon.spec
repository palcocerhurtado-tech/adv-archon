# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for ADV ARCHON Desktop (.app bundle for macOS).

Build:
    pip install pyinstaller
    pyinstaller archon.spec

Output:
    dist/ADV ARCHON.app
"""
import sys
from pathlib import Path

SRC = Path("src")

block_cipher = None

a = Analysis(
    [str(SRC / "adv_archon" / "desktop_entry.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        # Resources bundled inside the app
        (str(SRC / "adv_archon" / "resources"), "adv_archon/resources"),
        (str(SRC / "adv_archon" / "prompts"),   "adv_archon/prompts")
            if (SRC / "adv_archon" / "prompts").exists() else ("", ""),
    ],
    hiddenimports=[
        # PySide6 modules loaded at runtime
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        # Desktop modules
        "adv_archon.desktop.app",
        "adv_archon.desktop.workers",
        "adv_archon.desktop.warmup_agent",
        "adv_archon.desktop.compliance_session",
        "adv_archon.desktop.branding",
        "adv_archon.desktop.bundle",
        "adv_archon.desktop.models",
        "adv_archon.desktop.presenters",
        "adv_archon.desktop.runtime",
        # Core
        "adv_archon.core.config",
        "adv_archon.core.llm",
        "adv_archon.core.runtime",
        "adv_archon.core.agent",
        "adv_archon.core.memory",
        "adv_archon.core.knowledge",
        "adv_archon.core.pgou_store",
        "adv_archon.core.geo_store",
        "adv_archon.core.site_context",
        "adv_archon.core.report_generator",
        # Integrations
        "adv_archon.integrations.gemini",
        "adv_archon.integrations.ollama",
        "adv_archon.integrations.nominatim",
        "adv_archon.integrations.catastro",
        # Tools
        "adv_archon.tools.urban_compliance",
        "adv_archon.tools.urban_plan",
        "adv_archon.tools.pgou_scraper",
        "adv_archon.tools.geo_tools",
        "adv_archon.tools.files",
        "adv_archon.tools.knowledge_tools",
        "adv_archon.tools.memory_tools",
        "adv_archon.tools.web",
        # sentence-transformers backend
        "sentence_transformers",
        "torch",
        "transformers",
        # PDF parsing
        "pypdf",
        "pdfplumber",
        # Misc
        "httpx",
        "structlog",
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Don't bundle server-side API (not needed in desktop app)
        "fastapi",
        "uvicorn",
        # Heavy unused backends
        "tensorflow",
        "keras",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ADV ARCHON",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=True,    # macOS open-with support
    target_arch=None,       # universal2 via build script
    codesign_identity=None, # unsigned; user can notarise separately
    entitlements_file=None,
    icon="src/adv_archon/resources/branding/archon-logo.png",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["PySide6"],   # don't UPX Qt libs — they break
    name="ADV ARCHON",
)

app = BUNDLE(
    coll,
    name="ADV ARCHON.app",
    icon="src/adv_archon/resources/branding/archon-logo.png",
    bundle_identifier="tech.palcocer.adv-archon",
    version="1.0.0",
    info_plist={
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,   # supports dark mode
        "LSMinimumSystemVersion": "13.0",
        "CFBundleDisplayName": "ADV ARCHON",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHumanReadableCopyright": "© 2025 Pablo Alcocer",
        # Privacy strings — macOS requires these for any app using them
        "NSMicrophoneUsageDescription": "ADV ARCHON usa el micrófono para dictado por voz.",
        "NSCameraUsageDescription":
            "ADV ARCHON puede usar la cámara para análisis visual local cuando lo solicites.",
        "NSDocumentsFolderUsageDescription":
            "ADV ARCHON accede a documentos locales para analizarlos.",
    },
)
