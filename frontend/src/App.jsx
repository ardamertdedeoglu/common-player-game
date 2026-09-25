import React, { useState, useEffect, useRef } from 'react';
import confetti from 'canvas-confetti';
import {
  Trophy, Clock, Search, Users, Zap, CheckCircle2,
  Copy, RotateCcw, Volume2, VolumeX, Shield, Play, Flame, ExternalLink
} from 'lucide-react';
import './App.css';
import { playWhistle, playTick, playCorrect, playWrong } from './soundFx';

const isLocal = window.location.hostname === 'localhost';
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE_URL = isLocal
  ? `${protocol}//localhost:8000/ws`
  : `${protocol}//${window.location.host}/ws`;

const API_BASE_URL = isLocal
  ? 'http://localhost:8000/api'
  : '/api';

export default function App() {
  const [playerName, setPlayerName] = useState(() => localStorage.getItem('cp_player_name') || 'Futbolsever');
  const [roomCodeInput, setRoomCodeInput] = useState('');
  const [targetScore, setTargetScore] = useState(3);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Connection & Room state
  const [inGame, setInGame] = useState(false);
  const [roomState, setRoomState] = useState(null);
  const [myPlayerId, setMyPlayerId] = useState(null);
  const [copied, setCopied] = useState(false);

  // Team selection search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [popularTeams, setPopularTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [isSearching, setIsSearching] = useState(false);

  // Round active guess state
  const [guessInput, setGuessInput] = useState('');
  const [guessFeedback, setGuessFeedback] = useState(null);
  const [isInputShaking, setIsInputShaking] = useState(false);
  const [revealCountdown, setRevealCountdown] = useState(null);

  const wsRef = useRef(null);
  const guessInputRef = useRef(null);

  // Save player name
  useEffect(() => {
    localStorage.setItem('cp_player_name', playerName);
  }, [playerName]);

  // Load popular teams on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/popular-teams`)
      .then(res => res.json())
      .then(data => setPopularTeams(data))
      .catch(() => {});
  }, []);

  // Debounced search for teams
  useEffect(() => {
    if (searchQuery.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(() => {
      setIsSearching(true);
      fetch(`${API_BASE_URL}/search-teams?q=${encodeURIComponent(searchQuery)}`)
        .then(res => res.json())
        .then(data => {
          setIsSearching(false);
          if (data.success) {
            setSearchResults(data.results || []);
          }
        })
        .catch(() => setIsSearching(false));
    }, 280);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Connect to WebSocket room
  const connectToRoom = (roomId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `${WS_BASE_URL}/${roomId.toUpperCase()}/${encodeURIComponent(playerName.trim() || 'Oyuncu')}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setInGame(true);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWsMessage(message);
      } catch (err) {
        console.error("WS Parse error:", err);
      }
    };

    ws.onclose = () => {
      setInGame(false);
      setRoomState(null);
    };
  };

  const handleWsMessage = (msg) => {
    const { type, data } = msg;

    if (type === 'PLAYER_JOINED') {
      setRoomState(data.state);
      // Determine myPlayerId if not set
      if (!myPlayerId && data.player) {
        // Last joined is me or matched by name
        setMyPlayerId(data.player.id);
      }
    } else if (type === 'STATE_UPDATE') {
      setRoomState(data);
      if (data.status === 'ROUND_ACTIVE') {
        if (soundEnabled) playWhistle();
        setGuessFeedback(null);
        setTimeout(() => {
          if (guessInputRef.current) guessInputRef.current.focus();
        }, 100);
      } else if (data.status === 'GAME_OVER') {
        if (soundEnabled) playCorrect();
        confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 } });
      } else if (data.status === 'TEAM_SELECTION') {
        setSelectedTeam(null);
        setSearchQuery('');
        setSearchResults([]);
      }
    } else if (type === 'TIMER_TICK') {
      if (soundEnabled && data.timer <= 5 && data.timer > 0) {
        playTick();
      }
      setRoomState(prev => prev ? { ...prev, timer: data.timer } : prev);
    } else if (type === 'PRE_ROUND_TICK') {
      setRevealCountdown(data.count);
      if (soundEnabled) playTick();
    } else if (type === 'GUESS_RESULT') {
      if (data.correct) {
        if (soundEnabled) playCorrect();
      } else {
        if (soundEnabled) playWrong();
        setGuessFeedback(data.message || 'Yanlış oyuncu!');
        setIsInputShaking(true);
        setTimeout(() => setIsInputShaking(false), 500);
      }
    } else if (type === 'ERROR') {
      alert(data.message);
    }
  };

  // Actions
  const handleCreateRoom = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/create-room`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_score: targetScore })
      });
      const data = await res.json();
      if (data.success) {
        connectToRoom(data.room_id);
      }
    } catch (err) {
      alert("Sunucuya bağlanılamadı: " + err);
    }
  };

  const handleJoinRoom = () => {
    const code = roomCodeInput.trim().toUpperCase();
    if (!code) {
      alert("Lütfen bir oda kodu giriniz!");
      return;
    }
    connectToRoom(code);
  };

  const handleSendReady = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'READY' }));
    }
  };

  const handleSelectTeam = (team) => {
    setSelectedTeam(team);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'SELECT_TEAM',
        data: { team }
      }));
    }
  };

  const handleSendGuess = (e) => {
    e.preventDefault();
    const clean = guessInput.trim();
    if (!clean || !wsRef.current) return;

    wsRef.current.send(JSON.stringify({
      type: 'GUESS',
      data: { guess: clean }
    }));
    setGuessInput('');
  };

  const handleRematch = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'REMATCH' }));
    }
  };

  const copyRoomCode = () => {
    if (roomState?.room_id) {
      navigator.clipboard.writeText(roomState.room_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const openSecondTabForTesting = () => {
    window.open(window.location.href, '_blank');
  };

  const isMyTurn = () => {
    if (!roomState || !myPlayerId) return false;
    const me = roomState.players.find(p => p.id === myPlayerId);
    return me ? !me.has_selected_team : true;
  };

  const p1 = roomState?.players?.[0];
  const p2 = roomState?.players?.[1];

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="logo-badge">
          <div className="logo-icon">⚽</div>
          <div className="logo-text">
            <h1>COMMON PLAYER 1v1</h1>
            <p>Real-Time Football Quiz Arena</p>
          </div>
        </div>

        <div className="header-actions">
          <button
            className="btn-icon"
            onClick={() => setSoundEnabled(!soundEnabled)}
            title={soundEnabled ? 'Sesi Kapat' : 'Sesi Aç'}
          >
            {soundEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
            <span>{soundEnabled ? 'Ses Açık' : 'Sessiz'}</span>
          </button>

          {inGame && (
            <button
              className="btn-icon"
              onClick={() => {
                if (wsRef.current) wsRef.current.close();
                setInGame(false);
              }}
            >
              <RotateCcw size={16} />
              <span>Ayrıl</span>
            </button>
          )}
        </div>
      </header>

      {/* Screen 1: Home / Setup (Not in room) */}
      {!inGame && (
        <main className="home-grid">
          <div className="hero-box glass-panel scale-up">
            <div className="hero-tag">
              <Zap size={15} /> CANLI 1V1 FUTBOL DÜELLOSU
            </div>
            <h2 className="hero-title">
              İki Takım, <span>Ortak Bir Oyuncu!</span>
            </h2>
            <p className="hero-desc">
              Arkadaşınla aynı odaya bağlan. Her raunt 15 saniyede takımlarınızı seçin, iki kulüpte de forma giymiş ortak futbolcuyu <strong>en hızlı yazan puanı kapsın!</strong>
            </p>

            <div className="rules-list">
              <div className="rule-item">
                <CheckCircle2 size={18} color="var(--accent-green)" />
                <span>15 saniyede istediğin takımı Transfermarkt'tan aratıp seç.</span>
              </div>
              <div className="rule-item">
                <CheckCircle2 size={18} color="var(--accent-green)" />
                <span>İki takım ekranda açıldığı an geri sayım başlar.</span>
              </div>
              <div className="rule-item">
                <CheckCircle2 size={18} color="var(--accent-green)" />
                <span>Ortak oyuncunun adını ilk yazan raundun galibi olur!</span>
              </div>
            </div>
          </div>

          <div className="action-box glass-panel scale-up">
            <div className="input-group">
              <label>Oyuncu Adınız</label>
              <input
                id="player-name-input"
                type="text"
                className="custom-input"
                placeholder="Örn: Arda, Alex, Hagi..."
                value={playerName}
                onChange={e => setPlayerName(e.target.value)}
                maxLength={20}
              />
            </div>

            <div className="input-group">
              <label>Hedef Galibiyet Puanı</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{
                    flex: 1,
                    borderColor: targetScore === 3 ? 'var(--accent-green)' : 'var(--border-subtle)',
                    background: targetScore === 3 ? 'rgba(16, 185, 129, 0.2)' : 'transparent'
                  }}
                  onClick={() => setTargetScore(3)}
                >
                  3 Puana Ulaşan (Hızlı)
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{
                    flex: 1,
                    borderColor: targetScore === 5 ? 'var(--accent-green)' : 'var(--border-subtle)',
                    background: targetScore === 5 ? 'rgba(16, 185, 129, 0.2)' : 'transparent'
                  }}
                  onClick={() => setTargetScore(5)}
                >
                  5 Puana Ulaşan (Uzun)
                </button>
              </div>
            </div>

            <button
              id="create-room-btn"
              className="btn-primary"
              onClick={handleCreateRoom}
            >
              <Play size={20} fill="#fff" />
              <span>Yeni Oda Oluştur</span>
            </button>

            <div className="divider">
              <span>VEYA</span>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                id="join-code-input"
                type="text"
                className="custom-input"
                placeholder="Oda Kodu (Örn: TR901)"
                value={roomCodeInput}
                onChange={e => setRoomCodeInput(e.target.value.toUpperCase())}
                maxLength={6}
                style={{ textTransform: 'uppercase', letterSpacing: '2px', fontWeight: 'bold' }}
              />
              <button
                id="join-room-btn"
                className="btn-secondary"
                style={{ width: 'auto', padding: '0 24px' }}
                onClick={handleJoinRoom}
              >
                Katıl
              </button>
            </div>
          </div>
        </main>
      )}

      {/* Screen 2: In-Game Arena */}
      {inGame && roomState && (
        <main>
          {/* Top Scoreboard Bar */}
          <div className="scoreboard-bar glass-panel scale-up">
            <div className="score-player p1">
              <div className="player-avatar">
                {p1?.name?.[0]?.toUpperCase() || '1'}
              </div>
              <div>
                <div className="player-name-label">{p1?.name || 'Oyuncu 1 Bekleniyor...'}</div>
                <div className="player-badge-tag">{p1 ? (p1.id === myPlayerId ? 'Sen' : 'Rakip') : ''}</div>
                <div className="score-points">
                  {Array.from({ length: roomState.target_score }).map((_, i) => (
                    <div
                      key={i}
                      className={`point-dot p1 ${i < (p1?.score || 0) ? 'filled' : ''}`}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="score-center-timer">
              <div className="round-pill">Raunt {roomState.round_number || 1}</div>
              <div className="timer-circle">
                {roomState.timer ?? '--'}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                {roomState.status === 'TEAM_SELECTION' && 'Takım Seçimi'}
                {roomState.status === 'ROUND_ACTIVE' && 'Hızlı Yazma!'}
                {roomState.status === 'PRE_ROUND' && 'Başlıyor'}
                {roomState.status === 'LOBBY' && 'Lobi'}
                {roomState.status === 'ROUND_RESULT' && 'Raunt Sonu'}
                {roomState.status === 'GAME_OVER' && 'Maç Bitti'}
              </div>
            </div>

            <div className="score-player p2 right">
              <div className="player-avatar">
                {p2?.name?.[0]?.toUpperCase() || '2'}
              </div>
              <div>
                <div className="player-name-label">{p2?.name || 'Rakip Bekleniyor...'}</div>
                <div className="player-badge-tag">{p2 ? (p2.id === myPlayerId ? 'Sen' : 'Rakip') : ''}</div>
                <div className="score-points" style={{ justifyContent: 'flex-end' }}>
                  {Array.from({ length: roomState.target_score }).map((_, i) => (
                    <div
                      key={i}
                      className={`point-dot p2 ${i < (p2?.score || 0) ? 'filled' : ''}`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* PHASE 1: LOBBY (Waiting for Player 2 / Ready Up) */}
          {roomState.status === 'LOBBY' && (
            <div className="lobby-card glass-panel scale-up">
              <h2>Oda Hazırlandı!</h2>
              <p style={{ color: 'var(--text-muted)', marginTop: '6px' }}>
                Arkadaşını davet etmek için aşağıdaki oda kodunu paylaş:
              </p>

              <div className="room-code-badge" onClick={copyRoomCode}>
                <span>{roomState.room_id}</span>
                <Copy size={18} />
                <span style={{ fontSize: '0.8rem', letterSpacing: '0' }}>
                  {copied ? 'Kopyalandı!' : 'Kodu Kopyala'}
                </span>
              </div>

              <div className="players-slots">
                <div className="player-slot filled">
                  <div className="player-avatar" style={{ width: 50, height: 50 }}>
                    {p1?.name?.[0]?.toUpperCase()}
                  </div>
                  <strong>{p1?.name}</strong>
                  <span style={{ fontSize: '0.8rem', color: p1?.is_ready ? 'var(--accent-green)' : 'var(--text-dim)' }}>
                    {p1?.is_ready ? '✅ Hazır' : '⏳ Hazır Bekleniyor'}
                  </span>
                </div>

                <div className={`player-slot ${p2 ? 'filled' : ''}`}>
                  {p2 ? (
                    <>
                      <div className="player-avatar" style={{ width: 50, height: 50 }}>
                        {p2.name[0].toUpperCase()}
                      </div>
                      <strong>{p2.name}</strong>
                      <span style={{ fontSize: '0.8rem', color: p2.is_ready ? 'var(--accent-green)' : 'var(--text-dim)' }}>
                        {p2.is_ready ? '✅ Hazır' : '⏳ Hazır Bekleniyor'}
                      </span>
                    </>
                  ) : (
                    <>
                      <Users size={32} color="var(--text-dim)" />
                      <span style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>
                        2. Oyuncu Bekleniyor...
                      </span>
                      <button
                        className="btn-secondary"
                        style={{ fontSize: '0.8rem', padding: '6px 12px' }}
                        onClick={openSecondTabForTesting}
                      >
                        <ExternalLink size={14} /> İkinci Sekmede Test Et
                      </button>
                    </>
                  )}
                </div>
              </div>

              {roomState.players.length >= 2 && (
                <button
                  id="ready-btn"
                  className="btn-primary"
                  style={{ maxWidth: '300px', margin: '0 auto' }}
                  onClick={handleSendReady}
                >
                  <CheckCircle2 size={20} />
                  <span>Maça Hazırım!</span>
                </button>
              )}
            </div>
          )}

          {/* PHASE 2: TEAM SELECTION (15s Countdown) */}
          {roomState.status === 'TEAM_SELECTION' && (
            <div className="team-select-container glass-panel scale-up">
              <div className="select-header">
                <div>
                  <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>Takımını Seç!</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    İki takımdan birini sen, diğerini rakibin seçecek. Süre dolunca takımlar kilitlenir!
                  </p>
                </div>
                <div className="timer-tag">
                  <Clock size={20} />
                  <span>{roomState.timer}s</span>
                </div>
              </div>

              {selectedTeam ? (
                <div className="selected-team-card count-pop">
                  <div>
                    <span style={{ fontSize: '0.8rem', color: 'var(--accent-green)', fontWeight: 700, textTransform: 'uppercase' }}>
                      ✓ Seçtiğin Takım
                    </span>
                    <h3 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff' }}>
                      {selectedTeam.name}
                    </h3>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      {selectedTeam.country} {selectedTeam.league ? `• ${selectedTeam.league}` : ''}
                    </span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                      Rakibin seçimi bekleniyor... ⏳
                    </span>
                  </div>
                </div>
              ) : (
                <>
                  <div className="search-box-wrapper">
                    <input
                      id="team-search-input"
                      type="text"
                      className="custom-input"
                      placeholder="Transfermarkt'ta takım ara (Örn: Galatasaray, Real Madrid, Arsenal)..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      autoFocus
                    />
                    {isSearching && (
                      <div style={{ position: 'absolute', right: '16px', top: '16px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                        Aranıyor...
                      </div>
                    )}

                    {searchResults.length > 0 && (
                      <div className="search-results-dropdown">
                        {searchResults.map(team => (
                          <div
                            key={team.id}
                            className="result-item"
                            onClick={() => handleSelectTeam(team)}
                          >
                            <span style={{ fontWeight: 700 }}>{team.name}</span>
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              {team.country} {team.league ? `• ${team.league}` : ''}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="chips-title">Hızlı Seçim Popüler Kulüpler:</div>
                  <div className="popular-chips">
                    {popularTeams.slice(0, 16).map(team => (
                      <button
                        key={team.id}
                        className="chip-btn"
                        onClick={() => handleSelectTeam(team)}
                      >
                        {team.name}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* PHASE 3: PRE-ROUND (3s Reveal Countdown) */}
          {roomState.status === 'PRE_ROUND' && (
            <div className="vs-banner-box glass-panel count-pop">
              <div style={{ textTransform: 'uppercase', letterSpacing: '2px', color: 'var(--accent-gold)', fontWeight: 700 }}>
                Takımlar Eşleşti!
              </div>

              <div className="teams-vs-row">
                <div className="vs-club-card">
                  <span className="vs-club-name">{roomState.team1?.name}</span>
                  <span className="vs-club-country">{roomState.team1?.country}</span>
                </div>

                <div className="vs-badge-circle">VS</div>

                <div className="vs-club-card">
                  <span className="vs-club-name">{roomState.team2?.name}</span>
                  <span className="vs-club-country">{roomState.team2?.country}</span>
                </div>
              </div>

              <div className="reveal-count-number count-pop">
                {revealCountdown || 3}
              </div>
              <p style={{ color: 'var(--text-muted)' }}>Ortak futbolcuyu ilk yazan raundu alır!</p>
            </div>
          )}

          {/* PHASE 4: ACTIVE ROUND (25s Speed Guessing) */}
          {roomState.status === 'ROUND_ACTIVE' && (
            <div className="active-arena glass-panel scale-up">
              <div className="teams-vs-row" style={{ gap: '20px' }}>
                <div className="vs-club-card" style={{ padding: '16px' }}>
                  <span className="vs-club-name" style={{ fontSize: '1.3rem' }}>{roomState.team1?.name}</span>
                  <span className="vs-club-country">{roomState.team1?.country}</span>
                </div>
                <div className="vs-badge-circle" style={{ width: 44, height: 44, fontSize: '1.1rem' }}>VS</div>
                <div className="vs-club-card" style={{ padding: '16px' }}>
                  <span className="vs-club-name" style={{ fontSize: '1.3rem' }}>{roomState.team2?.name}</span>
                  <span className="vs-club-country">{roomState.team2?.country}</span>
                </div>
              </div>

              <form onSubmit={handleSendGuess} className={`guess-input-box ${isInputShaking ? 'shake' : ''}`}>
                <input
                  ref={guessInputRef}
                  id="guess-player-input"
                  type="text"
                  className="guess-input"
                  placeholder="Ortak bir futbolcu yaz ve Enter'a bas..."
                  value={guessInput}
                  onChange={e => setGuessInput(e.target.value)}
                  autoComplete="off"
                  autoFocus
                />
                <button id="submit-guess-btn" type="submit" className="guess-btn">
                  Gönder ⚡
                </button>
              </form>

              {guessFeedback && (
                <div className="feedback-alert error shake">
                  {guessFeedback}
                </div>
              )}

              <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                💡 İpucu: Tam isim veya yalnızca bilinen soyadını (örneğin: Sneijder, Batshuayi, Arda Turan) yazabilirsiniz.
              </div>
            </div>
          )}

          {/* PHASE 5: ROUND RESULT (Who scored & All common players) */}
          {roomState.status === 'ROUND_RESULT' && (
            <div className="result-card-winner glass-panel count-pop">
              {roomState.round_winner === 'DRAW' ? (
                <>
                  <div className="winner-banner-badge" style={{ borderColor: 'var(--accent-gold)', color: 'var(--accent-gold)' }}>
                    ⏱️ Süre Doldu!
                  </div>
                  <h3 style={{ fontSize: '1.8rem', fontWeight: 800 }}>Kimse Bilemedi!</h3>
                </>
              ) : (
                <>
                  <div className="winner-banner-badge">
                    🎉 Raundu Kazanan: {roomState.players.find(p => p.id === roomState.round_winner)?.name} (+1 Puan)
                  </div>
                  <div className="winning-player-highlight">
                    "{roomState.winning_guess}"
                  </div>
                </>
              )}

              {/* Show valid common players for both teams */}
              <div className="common-players-preview">
                <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                  Bu İki Takımda Oynamış Ortak Oyuncular ({roomState.all_common_players?.length || 0}):
                </div>
                <div className="common-players-grid">
                  {roomState.all_common_players?.map(p => (
                    <div
                      key={p.id}
                      className={`player-chip ${p.name.toLowerCase() === roomState.winning_guess?.toLowerCase() ? 'hit' : ''}`}
                    >
                      {p.name}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* PHASE 6: GAME OVER (Champion & Rematch) */}
          {roomState.status === 'GAME_OVER' && (
            <div className="victory-screen glass-panel count-pop">
              <Trophy className="trophy-glow-icon count-pop" />
              <div style={{ textTransform: 'uppercase', letterSpacing: '2px', color: 'var(--accent-gold)', fontWeight: 800 }}>
                ŞAMPİYON BELLİ OLDU!
              </div>

              <h2 style={{ fontSize: '2.6rem', fontWeight: 900 }}>
                🏆 {roomState.players.find(p => p.score >= roomState.target_score)?.name} KAZANDI!
              </h2>

              <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>
                Skor: {p1?.score} - {p2?.score} ({roomState.target_score} puana ilk ulaşan kazandı)
              </p>

              <button
                id="rematch-btn"
                className="btn-primary"
                style={{ maxWidth: '280px', marginTop: '16px' }}
                onClick={handleRematch}
              >
                <RotateCcw size={20} />
                <span>Rövanş Oyna</span>
              </button>
            </div>
          )}
        </main>
      )}
    </div>
  );
}
