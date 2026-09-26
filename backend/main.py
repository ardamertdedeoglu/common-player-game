import uuid
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.scraper import search_clubs
from services.popular_teams import POPULAR_CLUBS
from game_manager import game_manager, Player

app = FastAPI(title="Common Player 1v1 Arena", version="1.0.0")

# Enable CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/popular-teams")
async def get_popular_teams():
    return POPULAR_CLUBS


@app.get("/api/search-teams")
async def search_teams_endpoint(q: str = Query(..., min_length=2)):
    try:
        results = search_clubs(q, max_results=6)
        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


class CreateRoomRequest(BaseModel):
    target_score: Optional[int] = 3


@app.post("/api/create-room")
async def create_room_endpoint(req: CreateRoomRequest):
    room = game_manager.get_or_create_room(target_score=req.target_score)
    return {"success": True, "room_id": room.room_id, "target_score": room.target_score}


@app.get("/api/room/{room_id}")
async def check_room_endpoint(room_id: str):
    room = game_manager.rooms.get(room_id.upper().strip())
    if not room or len(room.players) == 0:
        return {"exists": False, "message": "Oda bulunamadı"}
    if len(room.players) >= 2:
        return {"exists": True, "full": True, "message": "Oda dolu"}
    return {
        "exists": True,
        "full": False,
        "status": room.status,
        "player_count": len(room.players),
    }


@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_game_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()

    room = game_manager.get_or_create_room(room_id)
    player_id = str(uuid.uuid4())[:8]
    clean_name = player_name.strip() or f"Oyuncu {len(room.players) + 1}"
    player = Player(player_id, clean_name, websocket)

    if not room.add_player(player):
        await websocket.send_json({
            "type": "ERROR",
            "data": {"message": "Bu oda dolu. Lütfen başka bir oda seçin veya yeni oda açın."}
        })
        await websocket.close()
        return

    # Send INIT event directly to this connected player
    await websocket.send_json({
        "type": "INIT",
        "data": {
            "player_id": player.id,
            "player": player.to_dict(),
            "state": room.get_state_payload(),
        }
    })

    # Broadcast updated room state to all players
    await room.broadcast("PLAYER_JOINED", {
        "player": player.to_dict(),
        "state": room.get_state_payload(),
        "message": f"🎉 {player.name} odaya katıldı!"
    })

    try:
        while True:
            msg = await websocket.receive_json()
            m_type = msg.get("type")
            m_data = msg.get("data", {})

            if m_type == "READY":
                player.is_ready = True
                await room.broadcast("STATE_UPDATE", room.get_state_payload())
                # If 2 players are ready and in LOBBY, start team selection!
                if len(room.players) == 2 and all(p.is_ready for p in room.players) and room.status == "LOBBY":
                    await game_manager.start_team_selection(room)

            elif m_type == "START_GAME":
                # Host starts game
                if len(room.players) >= 2 and room.status in ["LOBBY", "GAME_OVER"]:
                    for p in room.players:
                        p.score = 0
                        p.is_ready = True
                    await game_manager.start_team_selection(room)

            elif m_type == "SELECT_TEAM":
                # Player locks in their team choice during TEAM_SELECTION
                team = m_data.get("team")
                if team and room.status == "TEAM_SELECTION":
                    player.selected_team = team
                    await room.broadcast("PLAYER_SELECTED_TEAM", {
                        "player_id": player.id,
                        "player_name": player.name,
                        "team_name": team["name"],
                        "has_selected": True
                    })
                    # If both picked, transition immediately
                    if len(room.players) == 2 and all(p.selected_team for p in room.players):
                        if room.timer_task and not room.timer_task.done():
                            room.timer_task.cancel()
                        await game_manager.resolve_teams_and_start_round(room)

            elif m_type == "GUESS":
                guess_text = m_data.get("guess", "").strip()
                if guess_text:
                    await game_manager.handle_guess(room, player, guess_text)

            elif m_type == "REMATCH":
                room.reset_to_lobby()
                await room.broadcast("STATE_UPDATE", room.get_state_payload())

            elif m_type == "CHAT":
                chat_text = m_data.get("text", "").strip()
                if chat_text:
                    room.chat_messages.append({"sender": player.name, "text": chat_text})
                    await room.broadcast("CHAT_MESSAGE", {"sender": player.name, "text": chat_text})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS Exception for player {player_id} ({player.name}) in room {room_id}: {e}")
    finally:
        await game_manager.handle_player_disconnect(room.room_id, player_id)


# Mount static production build of frontend if exists
import os
from fastapi.staticfiles import StaticFiles

possible_dist_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"),
    os.path.join(os.getcwd(), "frontend", "dist"),
    os.path.abspath("frontend/dist"),
]

frontend_dist = next((p for p in possible_dist_paths if os.path.exists(p)), None)
if frontend_dist:
    print(f"INFO: Successfully mounted frontend from: {frontend_dist}")
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    print("WARNING: frontend/dist could not be found! Available in cwd:", os.listdir(os.getcwd()))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
