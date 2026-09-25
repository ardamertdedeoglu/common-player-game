import json
import os
import time
from typing import Optional, Dict, Any

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
DEFAULT_TTL_HOURS = 72


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)


def get_cached_club(club_id: str, max_age_hours: int = DEFAULT_TTL_HOURS) -> Optional[Dict[str, Any]]:
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
            return json.load(f)
    except Exception:
        return None


def set_cached_club(club_id: str, data: Dict[str, Any]) -> None:
    ensure_cache_dir()
    filepath = os.path.join(CACHE_DIR, f"club_{club_id}.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
