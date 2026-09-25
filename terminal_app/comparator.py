import unicodedata
from typing import List, Dict, Any


def normalize_text(text: str) -> str:
    """
    Normalize text for case-insensitive and Turkish/Latin diacritic-insensitive matching.
    e.g. 'Bülent Korkmaz' -> 'bulent korkmaz', 'Şener Özbayraklı' -> 'sener ozbayrakli'
    """
    if not text:
        return ""

    # Turkish specific map
    char_map = str.maketrans({
        "ı": "i", "I": "i", "İ": "i", "i": "i",
        "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u",
        "ş": "s", "Ş": "s",
        "ö": "o", "Ö": "o",
        "ç": "c", "Ç": "c",
    })
    mapped = text.translate(char_map).lower()

    # Further remove other accents (é -> e, á -> a, etc.)
    nfkd = unicodedata.normalize("NFKD", mapped)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def find_common_players(club1_data: Dict[str, Any], club2_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Find players who played for both clubs.
    Returns list of player dictionaries sorted by player name.
    """
    players1 = club1_data.get("players", {})
    players2 = club2_data.get("players", {})

    club1_name = club1_data.get("name", "Takım 1")
    club2_name = club2_data.get("name", "Takım 2")

    # Match strictly by unique Transfermarkt Player ID.
    # Transfermarkt IDs are globally unique per person. Different IDs represent different
    # people even if they share the exact same name (e.g. Eren Aydın ID 873534 vs ID 28992).
    common_ids = set(players1.keys()) & set(players2.keys())

    results: List[Dict[str, Any]] = []

    for p_id in common_ids:
        p1 = players1[p_id]
        p2 = players2.get(p_id, {})

        name = p1.get("name") or p2.get("name") or f"Oyuncu #{p_id}"
        profile_url = p1.get("profile_url") or p2.get("profile_url") or ""

        c1_seasons = p1.get("seasons", [])
        c2_seasons = p2.get("seasons", [])

        c1_transfers = p1.get("transfers", [])
        c2_transfers = p2.get("transfers", [])

        results.append({
            "id": p_id,
            "name": name,
            "profile_url": profile_url,
            "club1_name": club1_name,
            "club1_seasons": c1_seasons,
            "club1_transfers": c1_transfers,
            "club2_name": club2_name,
            "club2_seasons": c2_seasons,
            "club2_transfers": c2_transfers,
        })

    # Sort alphabetically by player name
    results.sort(key=lambda p: normalize_text(p["name"]))
    return results


def search_common_players(common_players: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Search player in common players list by query.
    Supports partial names, tokens, and Turkish character tolerance.
    """
    q_norm = normalize_text(query).strip()
    if not q_norm:
        return []

    q_tokens = q_norm.split()
    matched = []

    for p in common_players:
        p_norm = normalize_text(p["name"])

        # 1. Exact match
        if q_norm == p_norm:
            matched.append((0, p))
            continue

        # 2. Substring match
        if q_norm in p_norm:
            matched.append((1, p))
            continue

        # 3. All query tokens present in player name
        if all(token in p_norm for token in q_tokens):
            matched.append((2, p))
            continue

    # Sort by relevance tier, then alphabetically
    matched.sort(key=lambda x: (x[0], normalize_text(x[1]["name"])))
    return [item[1] for item in matched]
