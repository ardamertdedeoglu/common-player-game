import asyncio
import random
import string
import time
from typing import Dict, List, Optional, Any
from fastapi import WebSocket

from services.popular_teams import POPULAR_CLUBS
from services.scraper import get_club_data
from services.comparator import find_common_players, validate_guess


def generate_room_code(length: int = 5) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


class Player:
    def __init__(self, player_id: str, name: str, websocket: WebSocket):
        self.id = player_id
        self.name = name
        self.websocket = websocket
        self.score = 0
        self.selected_team: Optional[Dict[str, Any]] = None
        self.is_ready = False

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "is_ready": self.is_ready,
            "has_selected_team": self.selected_team is not None,
            "selected_team_name": self.selected_team["name"] if self.selected_team else None,
        }


class Room:
    def __init__(self, room_id: str, target_score: int = 3):
        self.room_id = room_id
        self.target_score = target_score
        self.players: List[Player] = []
        self.status = "LOBBY"  # LOBBY, TEAM_SELECTION, PRE_ROUND, ROUND_ACTIVE, ROUND_RESULT, GAME_OVER
        self.round_number = 0
        self.team1: Optional[Dict[str, Any]] = None
        self.team2: Optional[Dict[str, Any]] = None
        self.common_players: List[Dict[str, Any]] = []
        self.guessed_common_players: List[Dict[str, Any]] = []
        self.round_winner: Optional[str] = None  # player_id or "DRAW"
        self.winning_guess: Optional[str] = None
        self.timer_seconds = 0
        self.timer_task: Optional[asyncio.Task] = None
        self.chat_messages: List[Dict[str, Any]] = []

    def reset_to_lobby(self):
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        self.timer_task = None
        self.status = "LOBBY"
        self.round_number = 0
        self.team1 = None
        self.team2 = None
        self.common_players = []
        self.guessed_common_players = []
        self.round_winner = None
        self.winning_guess = None
        self.timer_seconds = 0
        for p in self.players:
            p.score = 0
            p.is_ready = False
            p.selected_team = None

    def reset(self):
        self.reset_to_lobby()
        self.players = []
        self.chat_messages = []

    def get_player(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    def add_player(self, player: Player) -> bool:
        if len(self.players) >= 2:
            return False
        self.players.append(player)
        return True

    def remove_player(self, player_id: str) -> Optional[Player]:
        removed = None
        for p in self.players:
            if p.id == player_id:
                removed = p
                break
        self.players = [p for p in self.players if p.id != player_id]
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
            self.timer_task = None
        return removed

    async def broadcast(self, event_type: str, data: Any):
        payload = {"type": event_type, "data": data, "timestamp": time.time()}
        disconnected = []
        for p in self.players:
            try:
                await p.websocket.send_json(payload)
            except Exception:
                disconnected.append(p.id)
        for pid in disconnected:
            self.remove_player(pid)
        if len(self.players) == 0:
            self.reset()

    def get_state_payload(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "status": self.status,
            "target_score": self.target_score,
            "round_number": self.round_number,
            "timer": self.timer_seconds,
            "players": [p.to_dict() for p in self.players],
            "team1": self.team1,
            "team2": self.team2,
            # common_players is intentionally hidden during ROUND_ACTIVE for anti-cheat!
            "common_players_count": len(self.common_players) if self.common_players else 0,
            "all_common_players": self.common_players if self.status in ["ROUND_RESULT", "GAME_OVER"] else [],
            "round_winner": self.round_winner,
            "winning_guess": self.winning_guess,
            "chat_messages": self.chat_messages[-15:],
        }


class GameManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def get_or_create_room(self, room_id: Optional[str] = None, target_score: int = 3) -> Room:
        if not room_id:
            room_id = generate_room_code()
            while room_id in self.rooms:
                room_id = generate_room_code()
        room_id = room_id.upper().strip()
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id, target_score=target_score)
        else:
            # If room exists but has 0 players, ensure it is completely reset!
            if len(self.rooms[room_id].players) == 0:
                self.rooms[room_id].reset()
                self.rooms[room_id].target_score = target_score
        return self.rooms[room_id]

    async def handle_player_disconnect(self, room_id: str, player_id: str):
        room = self.rooms.get(room_id)
        if not room:
            return

        removed_player = room.remove_player(player_id)
        player_name = removed_player.name if removed_player else "Bir oyuncu"

        if len(room.players) == 0:
            # If nobody is left, completely reset the lobby and remove from active rooms
            room.reset()
            if room_id in self.rooms:
                del self.rooms[room_id]
            print(f"INFO: Room {room_id} is now empty and has been reset and closed.")
        else:
            # 1 player remaining: reset state to LOBBY so game doesn't freeze
            was_in_game = room.status != "LOBBY"
            room.reset_to_lobby()

            message = (
                f"⚠️ {player_name} oyundan ayrıldı. Oyun durduruldu ve lobiye dönüldü."
                if was_in_game
                else f"⚠️ {player_name} lobiden ayrıldı."
            )

            await room.broadcast("PLAYER_LEFT", {
                "player_id": player_id,
                "player_name": player_name,
                "state": room.get_state_payload(),
                "message": message,
                "was_in_game": was_in_game,
            })
            # Also send explicit STATE_UPDATE to ensure state synchronization
            await room.broadcast("STATE_UPDATE", room.get_state_payload())

    async def start_team_selection(self, room: Room):
        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        room.status = "TEAM_SELECTION"
        room.round_number += 1
        room.team1 = None
        room.team2 = None
        room.common_players = []
        room.round_winner = None
        room.winning_guess = None
        for p in room.players:
            p.selected_team = None

        room.timer_seconds = 15
        await room.broadcast("STATE_UPDATE", room.get_state_payload())

        if room.timer_task and not room.timer_task.done():
            room.timer_task.cancel()

        room.timer_task = asyncio.create_task(self._team_selection_countdown(room))

    async def _team_selection_countdown(self, room: Room):
        try:
            while room.timer_seconds > 0:
                await asyncio.sleep(1)
                if len(room.players) < 2:
                    room.reset_to_lobby()
                    await room.broadcast("STATE_UPDATE", room.get_state_payload())
                    return
                room.timer_seconds -= 1
                await room.broadcast("TIMER_TICK", {"timer": room.timer_seconds})

                # Check if both players selected early
                if len(room.players) == 2 and all(p.selected_team for p in room.players):
                    break

            if len(room.players) < 2:
                room.reset_to_lobby()
                await room.broadcast("STATE_UPDATE", room.get_state_payload())
                return

            # If time ran out and a player didn't pick, assign random popular team
            available_popular = POPULAR_CLUBS.copy()
            random.shuffle(available_popular)

            if len(room.players) >= 1 and not room.players[0].selected_team:
                room.players[0].selected_team = available_popular.pop(0)
            if len(room.players) >= 2 and not room.players[1].selected_team:
                # ensure different team
                for pick in available_popular:
                    if pick["id"] != room.players[0].selected_team["id"]:
                        room.players[1].selected_team = pick
                        break

            await self.resolve_teams_and_start_round(room)
        except asyncio.CancelledError:
            pass

    async def resolve_teams_and_start_round(self, room: Room):
        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        room.team1 = room.players[0].selected_team
        room.team2 = room.players[1].selected_team

        # If somehow both picked exact same team, pick another for player 2
        if room.team1 and room.team2 and room.team1.get("id") == room.team2.get("id"):
            for pick in POPULAR_CLUBS:
                if pick["id"] != room.team1["id"]:
                    room.team2 = pick
                    room.players[1].selected_team = pick
                    break

        await room.broadcast("TEAMS_LOCKED", {
            "team1": room.team1,
            "team2": room.team2,
            "message": "Takımlar belirlendi! Veriler Transfermarkt'tan kontrol ediliyor..."
        })

        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        # Load transfer data in threadpool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        try:
            c1_data = await loop.run_in_executor(
                None, get_club_data, room.team1["slug"], room.team1["id"], room.team1["name"]
            )
            c2_data = await loop.run_in_executor(
                None, get_club_data, room.team2["slug"], room.team2["id"], room.team2["name"]
            )
            common = find_common_players(c1_data, c2_data)
        except Exception as e:
            common = []

        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        # If zero common players, pick a classic pair that definitely has common players
        if not common:
            classic_pairs = [
                ("141", "galatasaray-istanbul", "Galatasaray", "36", "fenerbahce-istanbul", "Fenerbahçe"),
                ("418", "real-madrid", "Real Madrid", "131", "fc-barcelona", "FC Barcelona"),
                ("11", "fc-arsenal", "Arsenal FC", "631", "chelsea-fc", "Chelsea FC"),
                ("46", "inter-mailand", "Inter Milan", "5", "ac-mailand", "AC Milan"),
            ]
            pair = random.choice(classic_pairs)
            room.team1 = {"id": pair[0], "slug": pair[1], "name": pair[2]}
            room.team2 = {"id": pair[3], "slug": pair[4], "name": pair[5]}
            c1_data = await loop.run_in_executor(None, get_club_data, pair[1], pair[0], pair[2])
            c2_data = await loop.run_in_executor(None, get_club_data, pair[4], pair[3], pair[5])
            common = find_common_players(c1_data, c2_data)

        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        room.common_players = common

        # Pre-round countdown (3 seconds)
        room.status = "PRE_ROUND"
        room.timer_seconds = 3
        await room.broadcast("STATE_UPDATE", room.get_state_payload())

        for sec in [3, 2, 1]:
            if len(room.players) < 2:
                room.reset_to_lobby()
                await room.broadcast("STATE_UPDATE", room.get_state_payload())
                return
            room.timer_seconds = sec
            await room.broadcast("PRE_ROUND_TICK", {"count": sec})
            await asyncio.sleep(1)

        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        # Start Round Active (25 seconds)
        room.status = "ROUND_ACTIVE"
        room.timer_seconds = 25
        await room.broadcast("STATE_UPDATE", room.get_state_payload())

        if room.timer_task and not room.timer_task.done():
            room.timer_task.cancel()

        room.timer_task = asyncio.create_task(self._round_countdown(room))

    async def _round_countdown(self, room: Room):
        try:
            while room.timer_seconds > 0:
                await asyncio.sleep(1)
                if len(room.players) < 2:
                    room.reset_to_lobby()
                    await room.broadcast("STATE_UPDATE", room.get_state_payload())
                    return
                room.timer_seconds -= 1
                await room.broadcast("TIMER_TICK", {"timer": room.timer_seconds})

            if len(room.players) < 2:
                room.reset_to_lobby()
                await room.broadcast("STATE_UPDATE", room.get_state_payload())
                return

            # Timer ran out with no winner
            room.round_winner = "DRAW"
            room.winning_guess = None
            await self.end_round(room)
        except asyncio.CancelledError:
            pass

    async def handle_guess(self, room: Room, player: Player, guess_text: str):
        if room.status != "ROUND_ACTIVE":
            return

        matched_player = validate_guess(guess_text, room.common_players)
        if matched_player:
            # Correct guess! Player wins the round!
            if room.timer_task and not room.timer_task.done():
                room.timer_task.cancel()

            player.score += 1
            room.round_winner = player.id
            room.winning_guess = matched_player["name"]

            await room.broadcast("GUESS_RESULT", {
                "correct": True,
                "winner_id": player.id,
                "winner_name": player.name,
                "player_name": matched_player["name"],
                "profile_url": matched_player.get("profile_url", ""),
            })

            await self.end_round(room)
        else:
            # Incorrect guess notification only to the guessing player
            try:
                await player.websocket.send_json({
                    "type": "GUESS_RESULT",
                    "data": {
                        "correct": False,
                        "guess": guess_text,
                        "message": f"'{guess_text}' ortak oyuncular arasında bulunamadı."
                    }
                })
            except Exception:
                pass

    async def end_round(self, room: Room):
        room.status = "ROUND_RESULT"
        await room.broadcast("STATE_UPDATE", room.get_state_payload())

        # Check for game over (first to target_score)
        game_winner = None
        for p in room.players:
            if p.score >= room.target_score:
                game_winner = p
                break

        await asyncio.sleep(5)  # 5 seconds to view round results and common players

        if len(room.players) < 2:
            room.reset_to_lobby()
            await room.broadcast("STATE_UPDATE", room.get_state_payload())
            return

        if game_winner:
            room.status = "GAME_OVER"
            await room.broadcast("STATE_UPDATE", {
                **room.get_state_payload(),
                "game_winner_id": game_winner.id,
                "game_winner_name": game_winner.name,
            })
        else:
            # Next round team selection
            await self.start_team_selection(room)


game_manager = GameManager()

