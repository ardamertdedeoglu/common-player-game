import unicodedata
from typing import List, Dict, Any, Optional


def normalize_text(text: str) -> str:
    if not text:
        return ""

    char_map = str.maketrans({
        "ı": "i", "I": "i", "İ": "i", "i": "i",
        "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u",
        "ş": "s", "Ş": "s",
        "ö": "o", "Ö": "o",
        "ç": "c", "Ç": "c",
    })
    mapped = text.translate(char_map).lower()
    nfkd = unicodedata.normalize("NFKD", mapped)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


def find_common_players(club1_data: Dict[str, Any], club2_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    players1 = club1_data.get("players", {})
    players2 = club2_data.get("players", {})

    club1_name = club1_data.get("name", "Takım 1")
    club2_name = club2_data.get("name", "Takım 2")

    # Strict match by Transfermarkt Player ID
    common_ids = set(players1.keys()) & set(players2.keys())
    results: List[Dict[str, Any]] = []

    for p_id in common_ids:
        p1 = players1[p_id]
        p2 = players2[p_id]

        name = p1.get("name") or p2.get("name") or f"Oyuncu #{p_id}"
        profile_url = p1.get("profile_url") or p2.get("profile_url") or ""

        results.append({
            "id": p_id,
            "name": name,
            "profile_url": profile_url,
            "club1_name": club1_name,
            "club1_seasons": p1.get("seasons", []),
            "club2_name": club2_name,
            "club2_seasons": p2.get("seasons", []),
        })

    results.sort(key=lambda p: normalize_text(p["name"]))
    return results


def validate_guess(guess: str, common_players: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Check if user guess matches any of the common players.
    Accepts:
    - Exact normalized name match ("wesley sneijder")
    - Last name / distinct single name match if unambiguous or clearly matches (e.g. "sneijder", "batshuayi", "hagi")
    - Token match (all words in guess exist in player name, e.g. "burak" in "burak yilmaz")
    """
    g_norm = normalize_text(guess)
    if not g_norm or len(g_norm) < 2:
        return None

    g_tokens = g_norm.split()

    # 1. Exact normalized match
    for p in common_players:
        p_norm = normalize_text(p["name"])
        if g_norm == p_norm:
            return p

    # 2. Token match (all words typed by user must be present in player name)
    for p in common_players:
        p_norm = normalize_text(p["name"])
        p_tokens = p_norm.split()
        if all(t in p_tokens for t in g_tokens):
            return p

    # 3. Substring match if length of guess is at least 4 characters
    if len(g_norm) >= 4:
        for p in common_players:
            p_norm = normalize_text(p["name"])
            if g_norm in p_norm:
                return p

    return None
