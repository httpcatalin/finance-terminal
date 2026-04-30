"""
Command registry + tokeniser for the POSIX-style option pricing CLI.

Syntax:  COMMAND TICKER [KEY=VALUE ...] [--flag ...]

Tokeniser splits e.g. "BSM GOOG K=150 T=0.25 --graph"
into  {cmd: "BSM", ticker: "GOOG", kwargs: {"K": 150.0, "T": 0.25}, flags: {"graph"}}

Commands are registered via the @register decorator with a typed param schema.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ParsedCommand:
    cmd: str
    ticker: str | None
    kwargs: dict[str, Any]
    flags: set[str]


@dataclass
class CommandSpec:
    name: str
    aliases: list[str]
    params: dict[str, type]   # KEY → expected type
    handler: Callable
    description: str = ""


class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, CommandSpec] = {}  # canonical name → spec
        self._alias_map: dict[str, str] = {}         # alias (lower) → canonical

    def register(
        self,
        name: str,
        aliases: list[str] | None = None,
        params: dict[str, type] | None = None,
        description: str = "",
    ):
        """Decorator to register a command handler."""
        aliases = aliases or []
        params = params or {}

        def decorator(fn: Callable) -> Callable:
            spec = CommandSpec(
                name=name.upper(),
                aliases=[a.lower() for a in aliases],
                params=params,
                handler=fn,
                description=description,
            )
            self._commands[name.upper()] = spec
            self._alias_map[name.lower()] = name.upper()
            for alias in aliases:
                self._alias_map[alias.lower()] = name.upper()
            return fn

        return decorator

    def resolve(self, name: str) -> CommandSpec | None:
        canon = self._alias_map.get(name.lower())
        if canon:
            return self._commands[canon]
        return None

    def suggest(self, name: str) -> list[str]:
        all_names = list(self._alias_map.keys())
        return difflib.get_close_matches(name.lower(), all_names, n=3, cutoff=0.5)

    def all_commands(self) -> list[CommandSpec]:
        return list(self._commands.values())


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_KV_PATTERN = re.compile(r"^([A-Za-z_]\w*)=(.+)$")
_FLAG_PATTERN = re.compile(r"^--([A-Za-z_]\w*)$")


def tokenise(raw: str) -> ParsedCommand:
    """Split a raw command string into structured parts."""
    parts = raw.strip().split()
    if not parts:
        raise ValueError("Empty command")

    cmd = parts[0].upper()
    ticker = None
    kwargs: dict[str, Any] = {}
    flags: set[str] = set()

    i = 1
    # Second token: ticker if it looks like one (all-alpha, 1-5 chars)
    if i < len(parts) and re.match(r"^[A-Za-z]{1,5}$", parts[i]) and "=" not in parts[i] and not parts[i].startswith("--"):
        ticker = parts[i].upper()
        i += 1

    while i < len(parts):
        token = parts[i]

        # --flag
        flag_m = _FLAG_PATTERN.match(token)
        if flag_m:
            flags.add(flag_m.group(1).lower())
            i += 1
            continue

        # KEY=VALUE
        kv_m = _KV_PATTERN.match(token)
        if kv_m:
            key = kv_m.group(1)
            val_str = kv_m.group(2)
            kwargs[key] = _parse_value(val_str)
            i += 1
            continue

        # Positional strategy name like "bull-spread" or bare value — store raw
        kwargs.setdefault("_positional", []).append(token)
        i += 1

    return ParsedCommand(cmd=cmd, ticker=ticker, kwargs=kwargs, flags=flags)


def _parse_value(s: str) -> int | float | str:
    """Attempt to parse as number, otherwise return string."""
    # Percentage
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s
