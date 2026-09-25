import json
import os
import time
from typing import Optional, Dict, Any

import sys

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_DIR = os.path.join(BASE_DIR, ".cache")
DEFAULT_TTL_HOURS = 72  # 3 days cache


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)


def get_cached_club(club_id: str, max_age_hours: int = DEFAULT_TTL_HOURS) -> Optional[Dict[str, Any]]:
    """Return cached club data if available and not expired."""
    ensure_cache_dir()
    filepath = os.path.join(CACHE_DIR, f"club_{club_id}.json")
    if not os.path.exists(filepath):
        return None

    try:
        file_mtime = os.path.getmtime(filepath)
        age_hours = (time.time() - file_mtime) / 3600.0
        if age_hours > max_age_hours:
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception:
        return None


def set_cached_club(club_id: str, data: Dict[str, Any]) -> None:
    """Save club data into cache file."""
    ensure_cache_dir()
    filepath = os.path.join(CACHE_DIR, f"club_{club_id}.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_cache() -> int:
    """Remove all cached files and return count of deleted items."""
    if not os.path.exists(CACHE_DIR):
        return 0
    count = 0
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(CACHE_DIR, filename)
            try:
                os.remove(filepath)
                count += 1
            except Exception:
                pass
    return count
