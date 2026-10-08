"""
Small disk cache for slow external data (Yahoo, NSE lists).

Each entry is stored as a pickle under data/cache/ with a
time-to-live. A failed fetch is never cached, and an expired
entry is used as a fallback if a fresh fetch fails.

Pickle is used because the cache only ever holds data this
application fetched itself; never load cache files from elsewhere.
"""

import hashlib
import os
import pickle
import time
from functools import wraps
from pathlib import Path


CACHE_DIR = Path(
    os.environ.get(
        "STOCK_ENGINE_CACHE_DIR",
        Path(__file__).resolve().parents[1] / "data" / "cache"
    )
)

# Set STOCK_ENGINE_CACHE=0 to disable (e.g. in tests).
ENABLED = os.environ.get("STOCK_ENGINE_CACHE", "1") != "0"

HOUR = 3600
DAY = 24 * HOUR


def _path(namespace, key):
    digest = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:20]
    return CACHE_DIR / namespace / f"{digest}.pkl"


def _read(path):
    try:
        with open(path, "rb") as handle:
            return pickle.load(handle)
    except Exception:
        return None


def _is_empty(value):
    if value is None:
        return True
    if hasattr(value, "empty"):
        return bool(value.empty)
    if isinstance(value, (dict, list)):
        return len(value) == 0
    return False


def cached(namespace, ttl_seconds):
    """
    Decorator: cache a function's result on disk, keyed by its
    arguments. Empty results (failed fetches) are not stored.
    """

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if not ENABLED:
                return function(*args, **kwargs)

            # The function's identity is part of the key, so two cached
            # functions with the same arguments never share an entry.
            path = _path(
                namespace,
                (function.__module__, function.__qualname__,
                 args, sorted(kwargs.items())),
            )

            entry = _read(path) if path.exists() else None

            if entry and time.time() - entry["time"] < ttl_seconds:
                return entry["value"]

            try:
                value = function(*args, **kwargs)
            except Exception:
                if entry:
                    return entry["value"]      # stale but usable
                raise

            if _is_empty(value):
                return entry["value"] if entry else value

            path.parent.mkdir(parents=True, exist_ok=True)

            temp = path.with_suffix(".tmp")

            with open(temp, "wb") as handle:
                pickle.dump({"time": time.time(), "value": value}, handle)

            os.replace(temp, path)

            return value

        return wrapper

    return decorator


def clear_cache(namespace=None):
    """Delete cached entries (all, or one namespace)."""

    root = CACHE_DIR / namespace if namespace else CACHE_DIR

    if not root.exists():
        return 0

    removed = 0

    for file in root.rglob("*.pkl"):
        file.unlink()
        removed += 1

    return removed
