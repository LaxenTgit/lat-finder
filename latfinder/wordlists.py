"""Wordlist loading — multi-list, dedup, shuffle, pattern filter."""

import random
import re
from pathlib import Path

_BUILTIN_DIR = Path(__file__).parent.parent / "wordlists"

_BUILTIN = {
    "default": _BUILTIN_DIR / "top1000.txt",
}


def _read(source: str) -> list[str]:
    path = _BUILTIN.get(source, Path(source))
    if not path.exists():
        raise FileNotFoundError(f"Wordlist not found: {path}")
    return [
        w.strip()
        for w in path.read_text(encoding="utf-8").splitlines()
        if w.strip() and not w.startswith("#")
    ]


def load_wordlist(
    sources: list[str],
    *,
    dedup: bool = True,
    shuffle: bool = False,
    filter_pattern: str | None = None,
) -> list[str]:
    """
    Load and merge one or more wordlists.

    Args:
        sources:        List of built-in names or file paths.
        dedup:          Remove duplicate entries (preserves first occurrence).
        shuffle:        Randomize order before returning.
        filter_pattern: Only keep words matching this regex.

    Returns:
        Processed list of subdomain words.
    """
    words: list[str] = []
    for src in sources:
        words.extend(_read(src))

    if dedup:
        seen: set[str] = set()
        unique: list[str] = []
        for w in words:
            if w not in seen:
                seen.add(w)
                unique.append(w)
        words = unique

    if filter_pattern:
        rx = re.compile(filter_pattern)
        words = [w for w in words if rx.search(w)]

    if shuffle:
        random.shuffle(words)

    return words
