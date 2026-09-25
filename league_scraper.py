import os
import sys
import time
import re
import sqlite3
import argparse
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

# Ensure UTF-8 printing on Windows
try:
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt

# Import existing backend scraper & cache
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))
from services.scraper import get_club_data, HEADERS, BASE_URL
from services.cache_manager import set_cached_club, ensure_cache_dir

console = Console()

# Pre-defined major leagues
MAJOR_LEAGUES = {
    "1": {"id": "TR1", "slug": "super-lig", "name": "Süper Lig", "country": "Türkiye"},
    "2": {"id": "GB1", "slug": "premier-league", "name": "Premier League", "country": "İngiltere"},
    "3": {"id": "ES1", "slug": "laliga", "name": "LaLiga", "country": "İspanya"},
    "4": {"id": "IT1", "slug": "serie-a", "name": "Serie A", "country": "İtalya"},
    "5": {"id": "L1",  "slug": "bundesliga", "name": "Bundesliga", "country": "Almanya"},
    "6": {"id": "FR1", "slug": "ligue-1", "name": "Ligue 1", "country": "Fransa"},
    "7": {"id": "TR2", "slug": "1-lig", "name": "1. Lig", "country": "Türkiye"},
    "8": {"id": "NL1", "slug": "eredivisie", "name": "Eredivisie", "country": "Hollanda"},
    "9": {"id": "PO1", "slug": "liga-portugal", "name": "Liga Portugal", "country": "Portekiz"},
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "football.db")


def init_sqlite_db(db_path: str = DB_PATH):
    """Initialize SQLite tables for fast query storage."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS clubs (
        id TEXT PRIMARY KEY,
        name TEXT,
        slug TEXT,
        country TEXT,
        league TEXT,
        total_players INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY,
        name TEXT,
        profile_url TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS club_players (
        club_id TEXT,
        player_id TEXT,
        seasons TEXT,
        transfers TEXT,
        PRIMARY KEY (club_id, player_id),
        FOREIGN KEY (club_id) REFERENCES clubs (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_club_players_club ON club_players(club_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_club_players_player ON club_players(player_id)")

    conn.commit()
    conn.close()


def save_club_to_sqlite(club_data: Dict[str, Any], country: str = "", league: str = "", db_path: str = DB_PATH):
    """Save parsed club data and players into SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    c_id = str(club_data["id"])
    c_name = club_data["name"]
    c_slug = club_data["slug"]
    players = club_data.get("players", {})

    cur.execute("""
    INSERT OR REPLACE INTO clubs (id, name, slug, country, league, total_players)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (c_id, c_name, c_slug, country, league, len(players)))

    for p_id, p in players.items():
        cur.execute("""
        INSERT OR IGNORE INTO players (id, name, profile_url)
        VALUES (?, ?, ?)
        """, (str(p_id), p["name"], p["profile_url"]))

        seasons_str = ",".join(p.get("seasons", []))
        transfers_str = ";".join(p.get("transfers", []))

        cur.execute("""
        INSERT OR REPLACE INTO club_players (club_id, player_id, seasons, transfers)
        VALUES (?, ?, ?, ?)
        """, (c_id, str(p_id), seasons_str, transfers_str))

    conn.commit()
    conn.close()


def fetch_league_clubs(league_code: str, league_slug: str) -> List[Dict[str, str]]:
    """Fetch list of all teams in a given league from Transfermarkt."""
    url = f"{BASE_URL}/{league_slug}/startseite/wettbewerb/{league_code}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Lig sayfası açılamadı ({url}): {e}")

    soup = BeautifulSoup(resp.content.decode("utf-8", errors="ignore"), "lxml")
    clubs: List[Dict[str, str]] = []
    seen = set()

    table = soup.find("table", class_="items")
    if not table:
        return []

    for a_tag in table.find_all("a", href=re.compile(r"/startseite/verein/\d+")):
        name = a_tag.get_text(strip=True)
        # Avoid row containing logo img or empty text
        if not name or a_tag.find("img"):
            continue

        m = re.search(r"/([^/]+)/startseite/verein/(\d+)", a_tag["href"])
        if not m:
            continue

        slug = m.group(1)
        club_id = m.group(2)

        if club_id in seen:
            continue
        seen.add(club_id)

        clubs.append({
            "id": club_id,
            "name": name,
            "slug": slug,
        })

    return clubs


def scrape_full_league(league_code: str, league_slug: str, league_name: str, country: str, delay_seconds: float = 1.8):
    """Download historical players for all teams in the league."""
    init_sqlite_db()
    ensure_cache_dir()

    console.print(f"\n[bold green]⚽ '{league_name}' ({country}) takımları taranıyor...[/bold green]")
    try:
        clubs = fetch_league_clubs(league_code, league_slug)
    except Exception as e:
        console.print(f"[bold red]Hata:[/] {e}")
        return

    if not clubs:
        console.print("[yellow]Bu ligde takım bulunamadı![/yellow]")
        return

    console.print(f"[cyan]Toplam {len(clubs)} takım bulundu. İndirme başlatılıyor...[/cyan]\n")

    total_players_scraped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task(f"[green]{league_name}[/green]", total=len(clubs))

        for idx, club in enumerate(clubs, 1):
            progress.update(task, description=f"[bold white]{club['name']}[/bold white] verileri çekiliyor ({idx}/{len(clubs)})...")

            try:
                # Scrape all transfers and players
                data = get_club_data(club["slug"], club["id"], club["name"], use_cache=False)
                # Save to JSON cache
                set_cached_club(club["id"], data)
                # Save to SQLite
                save_club_to_sqlite(data, country=country, league=league_name)

                player_count = len(data.get("players", {}))
                total_players_scraped += player_count
                progress.console.print(f"  ✓ [bold green]{club['name']}[/bold green]: [yellow]{player_count}[/yellow] geçmiş/mevcut oyuncu kaydedildi.")
            except Exception as e:
                progress.console.print(f"  ❌ [bold red]{club['name']}[/bold red] hatası: {e}")

            progress.advance(task)
            # Polite rate-limiting pause
            if idx < len(clubs):
                time.sleep(delay_seconds)

    console.print(Panel(
        f"🎉 [bold green]'{league_name}' başarıyla tamamlandı![/bold green]\n\n"
        f"• [white]Kaydedilen Takım Sayısı:[/] [bold yellow]{len(clubs)}[/]\n"
        f"• [white]Toplam Oyuncu Kaydı:[/] [bold cyan]{total_players_scraped}[/]\n"
        f"• [white]SQLite Veritabanı:[/] [dim]{DB_PATH}[/]\n"
        f"• [white]JSON Önbelleği:[/] [dim]backend/.cache/[/]",
        title="[bold yellow]Lig Tarama Raporu[/bold yellow]",
        border_style="green"
    ))


def interactive_menu():
    console.print(Panel(
        "🏆 [bold yellow]TRANSFERMARKT LİG OYUNCU TARAYICI[/bold yellow] 🏆\n"
        "Seçeceğiniz ligdeki tüm takımların geçmişten günümüze tüm oyuncularını çeker ve kaydeder.",
        border_style="bright_blue"
    ))

    table = Table(title="Mevcut Ligler", show_header=True, header_style="bold magenta")
    table.add_column("No", style="bold yellow", width=4, justify="center")
    table.add_column("Lig Adı", style="bold white")
    table.add_column("Ülke", style="green")
    table.add_column("Lig Kodu", style="cyan")

    for key, leg in MAJOR_LEAGUES.items():
        table.add_row(key, leg["name"], leg["country"], leg["id"])

    console.print(table)
    console.print("[dim]Özel bir lig için Transfermarkt lig kodunu doğrudan da girebilirsiniz (Örn: TR1, GB1, ES1...)[/dim]\n")

    choice = Prompt.ask("[bold green]Taramak istediğiniz lig no veya kodunu giriniz[/bold green]", default="1").strip()

    target_league = None
    if choice in MAJOR_LEAGUES:
        target_league = MAJOR_LEAGUES[choice]
    else:
        # Check by code
        for leg in MAJOR_LEAGUES.values():
            if leg["id"].upper() == choice.upper():
                target_league = leg
                break

    if not target_league:
        # Custom input
        custom_slug = Prompt.ask("Transfermarkt Lig URL Slug (Örn: super-lig, premier-league)").strip()
        custom_name = Prompt.ask("Lig Başlığı (Örn: Süper Lig)").strip()
        custom_country = Prompt.ask("Ülke (Örn: Türkiye)").strip()
        target_league = {
            "id": choice.upper(),
            "slug": custom_slug,
            "name": custom_name,
            "country": custom_country,
        }

    delay_input = Prompt.ask("İstekler arası bekleme süresi (saniye)", default="1.8")
    try:
        delay = float(delay_input)
    except ValueError:
        delay = 1.8

    scrape_full_league(
        target_league["id"],
        target_league["slug"],
        target_league["name"],
        target_league["country"],
        delay_seconds=delay
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape all historical players for a league.")
    parser.add_argument("--league", type=str, help="League code (e.g. TR1, GB1, ES1)")
    parser.add_argument("--delay", type=float, default=1.8, help="Delay in seconds between club requests")
    args = parser.parse_args()

    if args.league:
        code = args.league.upper()
        found = None
        for leg in MAJOR_LEAGUES.values():
            if leg["id"].upper() == code:
                found = leg
                break
        if found:
            scrape_full_league(found["id"], found["slug"], found["name"], found["country"], delay_seconds=args.delay)
        else:
            console.print(f"[red]Bilinmeyen lig kodu: {code}[/red]")
    else:
        interactive_menu()
