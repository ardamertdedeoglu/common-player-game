import re
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

from cache_manager import get_cached_club, set_cached_club

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

BASE_URL = "https://www.transfermarkt.com"


def search_clubs(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search for clubs on Transfermarkt by name query.
    Returns a list of dicts with: id, name, slug, country, league, url.
    """
    query_cleaned = query.strip()
    if not query_cleaned:
        return []

    encoded_query = urllib.parse.quote(query_cleaned)
    url = f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche?query={encoded_query}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Transfermarkt araması sırasında bağlantı hatası oluştu: {e}")

    soup = BeautifulSoup(resp.content.decode("utf-8", errors="ignore"), "lxml")

    results: List[Dict[str, str]] = []
    seen_ids = set()

    for box in soup.find_all("div", class_="box"):
        box_text = box.get_text()
        header = box.find(["h2", "div"], class_=re.compile(r"content-box-headline|table-header"))
        header_text = header.get_text(strip=True) if header else ""

        if "Clubs" in header_text or "Clubs" in box_text:
            table = box.find("table", class_="items")
            if not table:
                continue

            rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
            for r in rows:
                a_tag = r.find("a", href=lambda h: h and "/startseite/verein/" in h)
                if not a_tag:
                    continue

                club_name = a_tag.get_text(strip=True)
                if not club_name:
                    continue

                href = a_tag["href"]
                m = re.search(r"/([^/]+)/startseite/verein/(\d+)", href)
                if not m:
                    continue

                slug = m.group(1)
                club_id = m.group(2)

                if club_id in seen_ids:
                    continue
                seen_ids.add(club_id)

                # Find country and league
                country = ""
                country_img = r.find("img", class_="flaggenrahmen")
                if country_img and "title" in country_img.attrs:
                    country = country_img["title"].strip()

                league = ""
                # Typically row has league link or text
                for cell in r.find_all("td"):
                    league_link = cell.find("a", href=lambda h: h and "/wettbewerb/" in h)
                    if league_link and league_link.get_text(strip=True):
                        league = league_link.get_text(strip=True)
                        break

                results.append({
                    "id": club_id,
                    "name": club_name,
                    "slug": slug,
                    "country": country,
                    "league": league,
                    "url": f"{BASE_URL}{href}",
                })

                if len(results) >= max_results:
                    break

            break

    return results


def get_club_data(club_slug: str, club_id: str, club_name: str = "", use_cache: bool = True) -> Dict[str, Any]:
    """
    Fetch all historical transfers and players for a given club.
    Uses local cache if available and use_cache is True.
    """
    if use_cache:
        cached = get_cached_club(club_id)
        if cached:
            return cached

    url = f"{BASE_URL}/{club_slug}/alletransfers/verein/{club_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Kulüp transfer verileri çekilemedi ({club_slug}): {e}")

    soup = BeautifulSoup(resp.content.decode("utf-8", errors="ignore"), "lxml")

    players: Dict[str, Dict[str, Any]] = {}
    boxes = soup.find_all("div", class_="box")

    for b in boxes:
        h2 = b.find("h2")
        if not h2:
            continue
        title = h2.get_text(strip=True)

        # Parse season like 'Arrivals 23/24' or 'Departures 1926/27'
        match = re.search(r"(Arrivals|Departures)\s+(\d{2}/\d{2}|\d{4}/\d{2})", title)
        season = match.group(2) if match else ""
        transfer_type = match.group(1) if match else ""

        table = b.find("table")
        if not table:
            continue

        for tr in table.find_all("tr"):
            a_tag = tr.find("a", href=lambda h: h and "/profil/spieler/" in h)
            if not a_tag:
                continue

            name = a_tag.get_text(strip=True)
            if not name or name.isdigit() or len(name) < 2:
                continue

            href = a_tag["href"]
            m = re.search(r"/profil/spieler/(\d+)", href)
            if not m:
                continue
            p_id = m.group(1)

            if p_id not in players:
                players[p_id] = {
                    "id": p_id,
                    "name": name,
                    "profile_url": f"{BASE_URL}{href}",
                    "seasons": [],
                    "transfers": [],
                }

            if season and season not in players[p_id]["seasons"]:
                players[p_id]["seasons"].append(season)

            if season:
                transfer_desc = f"{'Geliş' if transfer_type == 'Arrivals' else 'Ayrılış'} {season}"
                if transfer_desc not in players[p_id]["transfers"]:
                    players[p_id]["transfers"].append(transfer_desc)

    # Also fetch current squad to guarantee any active player is present
    try:
        squad_url = f"{BASE_URL}/{club_slug}/kader/verein/{club_id}"
        resp_sq = requests.get(squad_url, headers=HEADERS, timeout=15)
        if resp_sq.status_code == 200:
            soup_sq = BeautifulSoup(resp_sq.content.decode("utf-8", errors="ignore"), "lxml")
            for a_tag in soup_sq.find_all("a", href=lambda h: h and "/profil/spieler/" in h):
                name = a_tag.get_text(strip=True)
                if not name or name.isdigit() or len(name) < 2:
                    continue
                m = re.search(r"/profil/spieler/(\d+)", a_tag["href"])
                if not m:
                    continue
                p_id = m.group(1)
                if p_id not in players:
                    players[p_id] = {
                        "id": p_id,
                        "name": name,
                        "profile_url": f"{BASE_URL}{a_tag['href']}",
                        "seasons": ["Mevcut Kadro"],
                        "transfers": ["Mevcut Kadro"],
                    }
                elif "Mevcut Kadro" not in players[p_id]["seasons"]:
                    players[p_id]["seasons"].append("Mevcut Kadro")
    except Exception:
        pass

    # Sort seasons for all players
    for p_id in players:
        players[p_id]["seasons"] = sorted(players[p_id]["seasons"])

    data = {
        "id": club_id,
        "name": club_name or club_slug,
        "slug": club_slug,
        "total_players": len(players),
        "players": players,
    }

    set_cached_club(club_id, data)
    return data


def get_player_profile(profile_url: str) -> Dict[str, str]:
    """
    Fetch comprehensive player details from their Transfermarkt profile.
    """
    try:
        resp = requests.get(profile_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"Hata": f"Oyuncu profili çekilemedi: {e}"}

    soup = BeautifulSoup(resp.content.decode("utf-8", errors="ignore"), "lxml")
    details: Dict[str, str] = {}

    # Check info-table
    info_table = soup.find("div", class_="info-table")
    if info_table:
        labels = [
            span.get_text(strip=True).rstrip(":")
            for span in info_table.find_all("span", class_="info-table__content--regular")
        ]
        values = [
            span.get_text(strip=True)
            for span in info_table.find_all("span", class_="info-table__content--bold")
        ]
        for l, v in zip(labels, values):
            # Translate common keys to Turkish
            label_tr = {
                "Name in home country": "Tam İsim",
                "Date of birth/Age": "Doğum Tarihi / Yaş",
                "Place of birth": "Doğum Yeri",
                "Height": "Boy",
                "Citizenship": "Uyruk",
                "Position": "Mevki",
                "Foot": "Kullandığı Ayak",
                "Current club": "Mevcut Kulüp",
                "Joined": "Kulübe Katılma",
                "Contract expires": "Sözleşme Bitiş",
            }.get(l, l)
            details[label_tr] = v

    # Fallback/Additional: Current Club from header
    club_span = soup.find("span", class_="data-header__club")
    if club_span and "Mevcut Kulüp" not in details:
        details["Mevcut Kulüp"] = club_span.get_text(strip=True)

    # Current market value
    mv_box = soup.find("div", class_="data-header__market-value-wrapper")
    if mv_box:
        mv_text = mv_box.get_text(" ", strip=True)
        # Extract e.g. €25.00m
        m = re.search(r"(€[0-9.,]+[km]?)", mv_text)
        if m:
            details["Güncel Piyasa Değeri"] = m.group(1)

    return details
