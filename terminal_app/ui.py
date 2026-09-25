import sys
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

# Initialize Rich console with UTF-8 support
console = Console()


def display_banner():
    """Display program header banner."""
    banner_text = Text()
    banner_text.append("⚽  TRANSFERMARKT ORTAK OYUNCU BULUCU  ⚽\n", style="bold yellow")
    banner_text.append("İki futbol takımında da forma giymiş ortak oyuncuları listeleme ve arama aracı\n", style="italic cyan")
    banner_text.append("Veri Kaynağı: Transfermarkt.com", style="dim white")

    console.print(Panel(
        banner_text,
        border_style="bright_blue",
        padding=(1, 2),
        expand=False
    ))


def prompt_team_search(prompt_title: str) -> str:
    """Ask user for team name to search."""
    console.print()
    team_query = Prompt.ask(f"[bold cyan]🔍 {prompt_title}[/bold cyan]")
    return team_query.strip()


def select_club_from_results(clubs: List[Dict[str, str]], query: str) -> Optional[Dict[str, str]]:
    """Present search results table and let the user pick one."""
    if not clubs:
        console.print(f"[bold red]❌ '{query}' için hiçbir kulüp bulunamadı![/bold red]")
        return None

    table = Table(
        title=f"'{query}' Arama Sonuçları",
        show_header=True,
        header_style="bold magenta",
        border_style="dim blue",
    )
    table.add_column("No", style="bold yellow", width=4, justify="center")
    table.add_column("Kulüp Adı", style="bold white")
    table.add_column("Ülke", style="green")
    table.add_column("Lig", style="cyan")
    table.add_column("Transfermarkt ID", style="dim", justify="right")

    for idx, c in enumerate(clubs, start=1):
        table.add_row(
            str(idx),
            c["name"],
            c.get("country") or "-",
            c.get("league") or "-",
            c["id"],
        )

    console.print(table)

    if len(clubs) == 1:
        console.print(f"[green]✓ Tek sonuç bulundu, otomatik seçildi: [bold]{clubs[0]['name']}[/bold][/green]")
        return clubs[0]

    while True:
        choice = Prompt.ask(
            "[bold green]Seçmek istediğiniz kulübün numarası[/bold green] [dim](Varsayılan: 1, İptal için: 0)[/dim]",
            default="1",
        )
        if choice == "0":
            return None
        if choice.isdigit():
            c_idx = int(choice)
            if 1 <= c_idx <= len(clubs):
                selected = clubs[c_idx - 1]
                console.print(f"[green]✓ Seçildi: [bold]{selected['name']}[/bold][/green]")
                return selected
        console.print("[red]Lütfen geçerli bir numara giriniz![/red]")


def display_comparison_summary(club1: Dict[str, Any], club2: Dict[str, Any], common_count: int):
    """Display nice summary box of the compared clubs and common players count."""
    text = Text()
    text.append(f"🏆 {club1['name']} ", style="bold green")
    text.append(" ✖  ", style="bold white")
    text.append(f"🏆 {club2['name']}\n\n", style="bold cyan")

    if common_count > 0:
        text.append("✨ Her iki takımda da forma giymiş toplam ", style="white")
        text.append(f"{common_count}", style="bold yellow underline")
        text.append(" ortak oyuncu bulundu!", style="white")
    else:
        text.append("ℹ️ Bu iki takımda da forma giymiş ortak oyuncu bulunamadı.", style="yellow")

    console.print(Panel(
        text,
        title="[bold yellow]Karşılaştırma Sonucu[/bold yellow]",
        border_style="green" if common_count > 0 else "yellow",
        padding=(1, 2)
    ))


def display_menu(common_count: int) -> str:
    """Show options menu and get user selection."""
    console.print()
    menu_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2)
    )
    menu_table.add_column("Key", style="bold yellow", width=5)
    menu_table.add_column("Desc", style="bold white")

    menu_table.add_row("[1]", "🔎 Ortak oyuncular listesinde oyuncu ara")
    menu_table.add_row("[2]", f"📋 Tüm ortak oyuncuları listele ({common_count} oyuncu)")
    menu_table.add_row("[3]", "🔄 Yeni takım karşılaştırması yap")
    menu_table.add_row("[0]", "🚪 Çıkış")

    panel = Panel(
        menu_table,
        title="[bold cyan]Yapmak İstediğiniz İşlemi Seçiniz[/bold cyan]",
        border_style="bright_blue",
        expand=False
    )
    console.print(panel)

    choice = Prompt.ask("[bold green]İşlem Seçimi[/bold green]", choices=["1", "2", "3", "0"], default="1")
    return choice


def display_common_players_table(
    common_players: List[Dict[str, Any]],
    club1_name: str,
    club2_name: str,
    page_size: int = 25
):
    """Display tabular list of common players with optional pagination."""
    if not common_players:
        console.print("[yellow]Listelenecek ortak oyuncu bulunamadı.[/yellow]")
        return

    total = len(common_players)
    start_idx = 0

    while start_idx < total:
        end_idx = min(start_idx + page_size, total)
        current_batch = common_players[start_idx:end_idx]

        table = Table(
            title=f"Ortak Oyuncular Listesi ({start_idx + 1}-{end_idx} / {total})",
            show_header=True,
            header_style="bold magenta",
            border_style="dim blue",
            expand=True
        )
        table.add_column("No", style="bold yellow", width=4, justify="center")
        table.add_column("Oyuncu Adı", style="bold white", min_width=22)
        table.add_column(f"{club1_name} Dönemleri", style="green", min_width=18)
        table.add_column(f"{club2_name} Dönemleri", style="cyan", min_width=18)
        table.add_column("TM ID", style="dim", width=8, justify="right")

        for idx, p in enumerate(current_batch, start=start_idx + 1):
            s1 = ", ".join(p.get("club1_seasons", [])) or "-"
            s2 = ", ".join(p.get("club2_seasons", [])) or "-"
            table.add_row(
                str(idx),
                p["name"],
                s1,
                s2,
                str(p.get("id", "-"))
            )

        console.print(table)

        if end_idx >= total:
            break

        next_action = Prompt.ask(
            f"[bold green]Sonraki {min(page_size, total - end_idx)} oyuncuyu göster?[/bold green] [dim](Devam için Enter, Menüye dönmek için 'm')[/dim]",
            default="e"
        )
        if next_action.lower() in ["m", "menu", "q", "exit"]:
            break
        start_idx = end_idx


def display_player_details_card(player: Dict[str, Any], profile_details: Dict[str, str]):
    """Display rich card of single player details."""
    text = Text()
    text.append(f"👤 {player['name']}\n", style="bold yellow underline")

    # Add profile details
    if "Tam İsim" in profile_details and profile_details["Tam İsim"] != player["name"]:
        text.append(f"• Tam İsim: {profile_details['Tam İsim']}\n", style="white")

    for key in [
        "Doğum Tarihi / Yaş", "Uyruk", "Mevki", "Doğum Yeri",
        "Boy", "Kullandığı Ayak", "Mevcut Kulüp", "Güncel Piyasa Değeri"
    ]:
        if key in profile_details:
            val = profile_details[key]
            text.append(f"• {key}: ", style="bold cyan")
            text.append(f"{val}\n", style="white")

    text.append("\n⚽ Kulüp Dönemleri:\n", style="bold green")
    s1 = ", ".join(player.get("club1_seasons", [])) or "Kayıtlı sezon detayı yok"
    s2 = ", ".join(player.get("club2_seasons", [])) or "Kayıtlı sezon detayı yok"
    text.append(f"  ▸ {player['club1_name']}: ", style="bold white")
    text.append(f"{s1}\n", style="bright_green")
    text.append(f"  ▸ {player['club2_name']}: ", style="bold white")
    text.append(f"{s2}\n", style="bright_cyan")

    if player.get("profile_url"):
        text.append(f"\n🔗 Profil: {player['profile_url']}", style="dim underline")

    console.print(Panel(
        text,
        title="[bold yellow]Oyuncu Bilgi Kartı[/bold yellow]",
        border_style="magenta",
        padding=(1, 2)
    ))
