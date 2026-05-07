"""File-level helpers: validation, path checks."""
from __future__ import annotations

import os


def is_writable_target(path: str) -> bool:
    """Best-effort check that we can write to `path`."""
    if os.path.isdir(path):
        return False
    parent = os.path.dirname(os.path.abspath(path)) or "."
    if not os.path.isdir(parent):
        return False
    if os.path.exists(path):
        return os.access(path, os.W_OK)
    return os.access(parent, os.W_OK)


def looks_like_pdf(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as fh:
            return fh.read(5) == b"%PDF-"
    except OSError:
        return False
