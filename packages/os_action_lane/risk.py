# -*- coding: utf-8 -*-
"""Risk classification — the axis the trust tiers gate on.

Conservative by construction: a `run` action is inspected for destructive shell patterns
and a catastrophic set (whole-disk / irreversible). When unsure, we round UP — an
unknown command is DESTRUCTIVE, never assumed safe. This is the honest default: the
gate can only protect if it never under-estimates.
"""
from __future__ import annotations

import re
from typing import Any

from .models import Action, RiskLevel

# whole-system / irreversible — even AUTONOMOUS confirms these once
_CATASTROPHIC = [
    re.compile(r"\brm\s+-[a-z]*\s*(/|~|/\*|\$HOME)(\s|$)"),        # rm -rf / , ~ , /*
    re.compile(r"\bmkfs\b"), re.compile(r"\bdd\b.*of=/dev/"),
    re.compile(r":\(\)\s*\{.*\|.*&\s*\}\s*;"),                      # fork bomb
    re.compile(r"\b(shutdown|poweroff|halt|reboot)\b"),
    re.compile(r"\buserdel\b|\bdeluser\b"),
    re.compile(r">\s*/dev/sd[a-z]"),
    re.compile(r"\bchmod\s+-R\s+0*\s+/\b"),
]
# data-loss / hard-to-undo
_DESTRUCTIVE = [
    re.compile(r"\brm\b"), re.compile(r"\bmv\b.*\s+/"), re.compile(r"\bkill(all)?\b"),
    re.compile(r"\bapt(-get)?\s+(remove|purge|autoremove)\b"),
    re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|push)\b"),
    re.compile(r">\s*[^&]"),                                        # truncating redirect
    re.compile(r"\btruncate\b|\bshred\b"),
]

# kind -> intrinsic risk when it is NOT a raw shell command
_KIND_RISK = {
    "list_windows": RiskLevel.READONLY, "read_file": RiskLevel.READONLY,
    "screenshot": RiskLevel.READONLY, "get_volume": RiskLevel.READONLY,
    "open_app": RiskLevel.REVERSIBLE, "focus_window": RiskLevel.REVERSIBLE,
    "type_text": RiskLevel.REVERSIBLE, "key": RiskLevel.REVERSIBLE,
    "set_volume": RiskLevel.REVERSIBLE, "move_mouse": RiskLevel.REVERSIBLE,
    "click": RiskLevel.REVERSIBLE, "close_window": RiskLevel.REVERSIBLE,
    "move_file": RiskLevel.DESTRUCTIVE, "delete_file": RiskLevel.DESTRUCTIVE,
    "kill_process": RiskLevel.DESTRUCTIVE, "write_file": RiskLevel.DESTRUCTIVE,
}


def _shell_risk(command: str) -> RiskLevel:
    c = command.strip()
    if not c:
        return RiskLevel.READONLY
    for pat in _CATASTROPHIC:
        if pat.search(c):
            return RiskLevel.CATASTROPHIC
    for pat in _DESTRUCTIVE:
        if pat.search(c):
            return RiskLevel.DESTRUCTIVE
    # a bare read-only viewer is reversible-or-lower; anything else is treated as
    # REVERSIBLE at least (it changes state), never assumed READONLY.
    readonly_heads = ("ls", "cat", "echo", "pwd", "whoami", "date", "wmctrl -l",
                      "grep", "find", "head", "tail", "which", "df", "free", "ps")
    if any(c.startswith(h) for h in readonly_heads) and ">" not in c and "|" not in c:
        return RiskLevel.READONLY
    return RiskLevel.REVERSIBLE


def classify(action: Action) -> RiskLevel:
    if action.kind == "run":
        return _shell_risk(str(action.args.get("command", "")))
    # a delete under a protected/system path escalates to catastrophic
    if action.kind in ("delete_file", "move_file"):
        path = str(action.args.get("path", ""))
        if path in ("/", "") or path.startswith(("/etc", "/usr", "/bin", "/boot", "/dev", "/sys")):
            return RiskLevel.CATASTROPHIC
    return _KIND_RISK.get(action.kind, RiskLevel.DESTRUCTIVE)  # unknown kind -> round up
