import sys
import os

# Ensure UTF-8 output encoding for Turkish characters on Windows
try:
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from rich.prompt import Prompt
from rich.table import Table

from scraper import search_clubs, get_club_data, get_player_profile
from comparator import find_common_players, search_common_players
from ui import (
    console,
    display_banner,
    prompt_team_search,
    select_club_from_results,
    display_comparison_summary,
    display_menu,
    display_common_players_table,
    display_player_details_card,
)


def select_team_workflow(prompt_label: str):
    """Guide user through searching and picking a team."""
    while True:
        query = prompt_team_search(prompt_label)
        if not query:
            console.print("[yellow]Takım adı boş olamaz![/yellow]")
            continue

        with console.status(f"[bold green]'{query}' Transfermarkt üzerinde aranıyor...[/bold green]", spinner="dots"):
            try:
                clubs = search_clubs(query)
            except Exception as e:
                console.print(f"[bold red]Hata:[/] {e}")
                continue

        selected_club = select_club_from_results(clubs, query)
        if selected_club:
            return selected_club
        console.print("[yellow]Lütfen tekrar arama yapınız.[/yellow]")


def handle_player_search(common_players, club1_name, club2_name):
    """Handle Option 1: Searching for a specific player in common players list."""
    while True:
        console.print()
        query = Prompt.ask("[bold cyan]🔎 Aramak istediğiniz oyuncu adı/soyadı[/bold cyan] [dim](Menüye dönmek için boş bırakın)[/dim]").strip()
        if not query:
            break

        matches = search_common_players(common_players, query)

        if not matches:
            console.print(f"\n[bold red]❌ '{query}'[/bold red] bu iki takımın ([bold]{club1_name}[/bold] & [bold]{club2_name}[/bold]) ortak oyuncuları arasında [bold red]bulunamadı[/bold red].")
            console.print("[dim]İpucu: Yalnızca her iki kulüpte de herhangi bir dönem oynamış futbolcular listelenir.[/dim]")
            continue

        console.print(f"\n[green]✓ '{query}' için [bold]{len(matches)}[/bold] eşleşme bulundu:[/green]")
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="dim blue",
            expand=True
        )
        table.add_column("No", style="bold yellow", width=4, justify="center")
        table.add_column("Oyuncu Adı", style="bold white", min_width=22)
        table.add_column(f"{club1_name} Dönemleri", style="green")
        table.add_column(f"{club2_name} Dönemleri", style="cyan")

        for idx, p in enumerate(matches, start=1):
            s1 = ", ".join(p.get("club1_seasons", [])) or "-"
            s2 = ", ".join(p.get("club2_seasons", [])) or "-"
            table.add_row(str(idx), p["name"], s1, s2)

        console.print(table)

        # Ask to view detailed profile
        if len(matches) == 1:
            ask_detail = Prompt.ask(
                f"[bold green]{matches[0]['name']} için Transfermarkt profil detaylarını görüntülemek ister misiniz?[/bold green] (E/h)",
                default="e"
            )
            if ask_detail.lower() in ["e", "evet", "y", "yes"]:
                with console.status("[bold green]Transfermarkt'tan oyuncu profili çekiliyor...[/bold green]", spinner="dots"):
                    details = get_player_profile(matches[0]["profile_url"])
                display_player_details_card(matches[0], details)
        else:
            sel = Prompt.ask(
                "[bold green]Detaylı profilini görmek istediğiniz oyuncu no[/bold green] [dim](Vazgeçmek için Enter)[/dim]",
                default=""
            ).strip()
            if sel.isdigit() and 1 <= int(sel) <= len(matches):
                chosen_player = matches[int(sel) - 1]
                with console.status(f"[bold green]{chosen_player['name']} profili çekiliyor...[/bold green]", spinner="dots"):
                    details = get_player_profile(chosen_player["profile_url"])
                display_player_details_card(chosen_player, details)


def handle_list_all(common_players, club1_name, club2_name):
    """Handle Option 2: List all common players and allow inspecting one."""
    display_common_players_table(common_players, club1_name, club2_name)

    # Allow inspecting a player
    choice = Prompt.ask(
        "\n[bold green]Detaylı profilini görüntülemek istediğiniz oyuncu numarası[/bold green] [dim](Menüye dönmek için Enter)[/dim]",
        default=""
    ).strip()
    if choice.isdigit() and 1 <= int(choice) <= len(common_players):
        chosen_player = common_players[int(choice) - 1]
        with console.status(f"[bold green]{chosen_player['name']} profili çekiliyor...[/bold green]", spinner="dots"):
            details = get_player_profile(chosen_player["profile_url"])
        display_player_details_card(chosen_player, details)


def main():
    display_banner()

    while True:
        console.print("\n[bold yellow]═══ 1. TAKIM SEÇİMİ ═══[/bold yellow]")
        club1 = select_team_workflow("1. Takım Adını Giriniz (Örn: Galatasaray, Real Madrid, Arsenal)")

        console.print("\n[bold yellow]═══ 2. TAKIM SEÇİMİ ═══[/bold yellow]")
        while True:
            club2 = select_team_workflow("2. Takım Adını Giriniz (Örn: Fenerbahçe, Barcelona, Chelsea)")
            if club2["id"] == club1["id"]:
                console.print("[bold red]Lütfen 1. takımdan farklı bir takım seçiniz![/bold red]")
                continue
            break

        # Fetch club data with spinners
        with console.status(f"[bold green]'{club1['name']}' oyuncu ve transfer geçmişi yükleniyor...[/bold green]", spinner="dots"):
            try:
                club1_data = get_club_data(club1["slug"], club1["id"], club1["name"])
            except Exception as e:
                console.print(f"[bold red]'{club1['name']}' verileri alınamadı:[/] {e}")
                continue

        with console.status(f"[bold green]'{club2['name']}' oyuncu ve transfer geçmişi yükleniyor...[/bold green]", spinner="dots"):
            try:
                club2_data = get_club_data(club2["slug"], club2["id"], club2["name"])
            except Exception as e:
                console.print(f"[bold red]'{club2['name']}' verileri alınamadı:[/] {e}")
                continue

        # Compute common players
        common_players = find_common_players(club1_data, club2_data)
        display_comparison_summary(club1, club2, len(common_players))

        if not common_players:
            retry = Prompt.ask("[bold green]Başka iki takım karşılaştırmak ister misiniz?[/bold green] (E/h)", default="e")
            if retry.lower() in ["e", "evet", "y", "yes"]:
                continue
            else:
                break

        # Menu loop for options
        while True:
            choice = display_menu(len(common_players))

            if choice == "1":
                # Option 1: Search player name in common players
                handle_player_search(common_players, club1["name"], club2["name"])
            elif choice == "2":
                # Option 2: List all common players
                handle_list_all(common_players, club1["name"], club2["name"])
            elif choice == "3":
                # New comparison
                break
            elif choice == "0":
                console.print("\n[bold cyan]Programdan çıkılıyor. İyi günler dileriz! ⚽👋[/bold cyan]")
                return


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[yellow]İşlem kullanıcı tarafından iptal edildi. Görüşmek üzere![/yellow]")
        sys.exit(0)
