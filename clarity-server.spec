# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Clarity server binary.

Produces a single-directory bundle named ``clarity-server`` that can run
all ``clarity.py`` subcommands (``web``, ``cli``, ``process``, etc.).

Build:
    pyinstaller clarity-server.spec

The resulting binary is intended to be registered as a Tauri ``externalBin``
sidecar.  For distribution, rename with the platform-architecture suffix
expected by Tauri (e.g. ``clarity-server-aarch64-apple-darwin``).
"""

import importlib.util
import platform
import sys
from pathlib import Path

block_cipher = None

# DLLs that UPX corrupts on Windows (causes "bad image" errors).
_upx_exclude = [
    "ucrtbase.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "python3*.dll",
    "api-ms-win-*.dll",
]

# ---------------------------------------------------------------------------
# Hidden imports: packages loaded dynamically by provider selection,
# plugin systems, or conditional imports that PyInstaller cannot trace.
# ---------------------------------------------------------------------------
hidden_imports = [
    # Web framework internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "websockets",
    "httptools",
    # LLM providers (conditionally imported at runtime)
    "anthropic",
    "openai",
    "azure.ai.inference",
    "azure.ai.inference.aio",
    "azure.ai.inference.models",
    "azure.core.credentials",
    "azure.identity",
    "claude_agent_sdk",
    # GitHub Copilot SDK
    "copilot",
    "copilot.client",
    "copilot.session",
    "copilot._jsonrpc",
    "copilot.generated",
    "copilot.generated.rpc",
    "copilot.generated.session_events",
    # Config and utilities
    "dotenv",
    "yaml",
    # Keyring (credential storage)
    "keyring",
    "keyring.backend",
    "keyring.backends",
    "keyring.backends.macOS",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.fail",
    # Document generation
    "docx",
    "mistune",
    # Pydantic (FastAPI models)
    "pydantic",
    "pydantic.deprecated.decorator",
    # Email-validator is pulled in by pydantic/fastapi
    "email_validator",
]

# ---------------------------------------------------------------------------
# Data files: non-Python assets that must be available at runtime.
# Each tuple is (source_path, dest_path_in_bundle).
# ---------------------------------------------------------------------------
# Locate the Copilot SDK's bundled CLI binary via Python's own import
# machinery — the previous hard-coded ``sys.prefix/Lib/site-packages``
# path worked only on Windows (which uses ``Lib`` rather than the
# ``lib/python3.X`` layout used on macOS / Linux), silently no-opping
# elsewhere and shipping a Mac desktop bundle without the binary.
# ``find_spec`` doesn't care about platform layout — it asks Python
# where the package actually lives.  We're running under the same
# venv PyInstaller will bundle from, so this is the source of truth.
_copilot_spec = importlib.util.find_spec("copilot")
_copilot_bin = (
    Path(_copilot_spec.origin).parent / "bin"
    if _copilot_spec is not None and _copilot_spec.origin
    else Path()
)

datas = [
    ("processes", "processes"),
    ("thinkers", "thinkers"),
    ("web/dist", "web/dist"),
    ("src/clarity_agent", "clarity_agent"),
]
if _copilot_bin.exists():
    datas.append((str(_copilot_bin), "copilot/bin"))
else:
    # Loud failure beats silent: if we ever lose track of the
    # copilot package (uninstalled, optional extra, etc.), surface
    # it at build time rather than producing a bundle that crashes
    # on the first GHCP call.
    print(
        f"WARNING: copilot/bin not found (looked for {_copilot_bin}). "
        "GHCP backend will not work in the bundled binary.",
        file=sys.stderr,
    )

a = Analysis(
    ["clarity.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not needed in the server binary
        "pywebview",
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "pytest",
        # Development tools
        "pyinstaller",
        "ruff",
        "mypy",
        "pyright",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if platform.system() == "Windows":
    # One-directory build for Windows.  DLLs live next to the exe in the
    # installed location instead of being extracted to %TEMP% at runtime,
    # which corporate WDAC / AppLocker policies typically block.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        name="clarity-server",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=_upx_exclude,
        console=True,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=_upx_exclude,
        name="clarity-server",
    )
else:
    # One-file build for macOS / Linux: everything packed into a single
    # executable.  At runtime PyInstaller extracts to a temp directory.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="clarity-server",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=_upx_exclude,
        console=True,
    )
