from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "apps" / "api" / "app" / "desktop_entry.py"
BINARIES_DIR = ROOT / "src-tauri" / "binaries"
RAW_DIST = ROOT / "build" / "pyinstaller" / "dist"
WORK_DIR = ROOT / "build" / "pyinstaller" / "work"
SPEC_DIR = ROOT / "build" / "pyinstaller" / "spec"
BASE_NAME = "homage-api"


PACKAGE_PATHS = [
    ROOT / "apps" / "api",
    ROOT / "packages" / "rag_engine",
    ROOT / "packages" / "guard",
    ROOT / "packages" / "ontology_forge",
    ROOT / "packages" / "datagate",
    ROOT / "packages" / "knowledge_bakery",
    ROOT / "packages" / "neuro_efficiency",
    ROOT / "packages" / "trainer",
    ROOT / "packages" / "model",
]


HIDDEN_IMPORTS = [
    "app.main",
    "app.desktop_entry",
    "app.routers.cloud_brain",
    "app.routers.datagate",
    "app.routers.factory",
    "app.routers.graphrag",
    "app.routers.guard",
    "app.routers.harvest",
    "app.routers.hybrid_network",
    "app.routers.learning",
    "app.routers.memory",
    "app.routers.neuro",
    "app.routers.ontology",
    "app.routers.oven",
    "app.routers.telemetry",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]


def run(command: list[str], *, cwd: Path = ROOT) -> str:
    completed = subprocess.run(command, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return completed.stdout


def target_triple() -> str:
    override = os.getenv("TAURI_TARGET_TRIPLE")
    if override:
        return override
    try:
        output = run(["rustc", "-vV"])
        for line in output.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        machine = platform.machine().lower()
        system = platform.system().lower()
        arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
        if system == "windows":
            return f"{arch}-pc-windows-msvc"
        if system == "darwin":
            return f"{arch}-apple-darwin"
        return f"{arch}-unknown-linux-gnu"
    raise RuntimeError("could not determine target triple")


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller.__main__  # type: ignore  # noqa: F401
    except Exception as exc:
        raise RuntimeError("PyInstaller is required. Install it with `python -m pip install pyinstaller`.") from exc


def build() -> Path:
    ensure_pyinstaller()
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIST.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ENTRYPOINT),
        "--name",
        BASE_NAME,
        "--onefile",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(RAW_DIST),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
    ]
    for path in PACKAGE_PATHS:
        command.extend(["--paths", str(path)])
    for name in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", name])
    run(command)

    suffix = ".exe" if platform.system().lower() == "windows" else ""
    built = RAW_DIST / f"{BASE_NAME}{suffix}"
    if not built.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {built}")
    target = BINARIES_DIR / f"{BASE_NAME}-{target_triple()}{suffix}"
    if target.exists():
        target.unlink()
    shutil.copy2(built, target)
    print(f"Built sidecar: {target}")
    return target


if __name__ == "__main__":
    build()
