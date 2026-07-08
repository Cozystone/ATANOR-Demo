# -*- coding: utf-8 -*-
"""Engine watchdog — the ports must never die again.

Watches the local companion engine (:8502) and the SPLATRA particle engine
(:8010). A service is restarted when it is (a) down, (b) unresponsive three
checks in a row, or (c) bloated past its memory ceiling — today's incident:
the engine grew to 8 GB and starved every request to death, killing chat for
hours. Restarts are safe by design: the selfhood layer RESUMES (continuity
keystone, born_at preserved), it is not reborn.

Run:  python scripts/engine_watchdog.py
Logs: data/watchdog.log
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(HERE, "data", "watchdog.log")

SERVICES = [
    {
        "name": "atanor-engine",
        "port": 8502,
        "health": "http://127.0.0.1:8502/health",
        # BASE footprint is ~5.2-6.2GB now (488k triple store + full stack) —
        # a 4GB cap put the engine in a permanent 60s kill-restart loop that
        # read as "random deaths" (measured 2026-07-08, data/watchdog.log).
        # Cap must sit well above base but still catch a true runaway.
        "rss_limit_mb": 12288,
        "cwd": HERE,
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", "8502", "--app-dir", "apps/api"],
    },
    {
        "name": "splatra",
        "port": 8010,
        "health": "http://127.0.0.1:8010/v1/models",
        "rss_limit_mb": 6144,          # torch models are heavy; higher ceiling
        # real text->3D. Without these flags every unknown prompt ("피카츄")
        # fell to a procedural hash-colored sphere (owner-reported pink blob).
        # TRIPOSR = learned single-image 3D reconstruction (measured: warm
        # ~6s / 170k gaussians on this GPU) — quality default; SD silhouette
        # lift (~1s) remains the automatic fallback if TripoSR errors.
        "env": {"SPLATRA_SD": "1", "SPLATRA_TRIPOSR": "1",
                "SPLATRA_TRIPOSR_DIR": r"C:\Users\anseo\.cache\splatra\TripoSR"},
        "cwd": r"C:\0.ASKIM ALL-VIN\26.SPLATRA",
        "cmd": [sys.executable, "-m", "uvicorn", "apps.plugin_api:app",
                "--port", "8010"],
    },
]

CHECK_EVERY_S = 30
FAILS_TO_RESTART = 3
HEALTH_TIMEOUT_S = 8


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def healthy(svc: dict) -> bool:
    try:
        with urllib.request.urlopen(svc["health"], timeout=HEALTH_TIMEOUT_S) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


# every helper spawn MUST be windowless: a background daemon that shells out
# every 30s otherwise flashes a console window each time — the exact
# "popup keeps appearing and dying" the owner reported
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def pid_on_port(port: int) -> int | None:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-NetTCPConnection -LocalPort {port} -State Listen "
             f"-ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"],
            capture_output=True, text=True, timeout=20,
            creationflags=NO_WINDOW).stdout.strip()
        return int(out) if out else None
    except Exception:
        return None


def rss_mb(pid: int) -> float:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).WorkingSet64"],
            capture_output=True, text=True, timeout=20,
            creationflags=NO_WINDOW).stdout.strip()
        return int(out) / (1024 * 1024) if out else 0.0
    except Exception:
        return 0.0


def restart(svc: dict) -> None:
    pid = pid_on_port(svc["port"])
    if pid:
        log(f"{svc['name']}: killing pid {pid}")
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, timeout=30, creationflags=NO_WINDOW)
        time.sleep(2)
    log(f"{svc['name']}: starting -> {' '.join(svc['cmd'])}")
    # CREATE_NO_WINDOW (a HIDDEN console the service's own children inherit),
    # never DETACHED_PROCESS: detached means NO console, so every child the
    # service shells out to (nvidia-smi, docker stats, git ...) allocates a
    # fresh VISIBLE console — the terminal-flash storm on the owner's screen.
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW
    env = {**os.environ, **svc["env"]} if svc.get("env") else None
    subprocess.Popen(svc["cmd"], cwd=svc["cwd"], creationflags=flags, env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    # SINGLETON lock: duplicate watchdogs once stacked 4-deep and their helper
    # shells flashed console windows nonstop. One localhost port = one instance.
    import socket

    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 18790))
        lock.listen(1)
    except OSError:
        print("another watchdog instance is already running; exiting")
        return

    fails = {s["name"]: 0 for s in SERVICES}
    log("watchdog up - " + ", ".join(s["name"] + ":" + str(s["port"]) for s in SERVICES))
    while True:
        for svc in SERVICES:
            name = svc["name"]
            ok = healthy(svc)
            reason = None
            if ok:
                fails[name] = 0
                pid = pid_on_port(svc["port"])
                if pid:
                    mem = rss_mb(pid)
                    if mem > svc["rss_limit_mb"]:
                        reason = f"memory {mem:.0f}MB > {svc['rss_limit_mb']}MB"
            else:
                fails[name] += 1
                if fails[name] >= FAILS_TO_RESTART:
                    reason = f"unhealthy x{fails[name]}"
            if reason:
                log(f"{name}: RESTART ({reason})")
                try:
                    restart(svc)
                except Exception as e:
                    log(f"{name}: restart failed: {e}")
                fails[name] = 0
                time.sleep(15)                 # grace for boot
        time.sleep(CHECK_EVERY_S)


if __name__ == "__main__":
    main()
