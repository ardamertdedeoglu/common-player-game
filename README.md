# ⚽ Common Player 1v1 | Ortak Futbolcu Düellosu

İki futbol kulübünde de forma giymiş ortak futbolcuları en hızlı tahmin edenin kazandığı, gerçek zamanlı (WebSocket) 1v1 çok oyunculu web oyunu ve terminal uygulaması.

---

## 🎮 Oyun Kuralları

1. **Oda Kur / Katıl:** Oyuncular 5 haneli benzersiz bir oda koduyla aynı maça bağlanır.
2. **15sn Takım Seçimi:** Her rauntta iki oyuncu da 15 saniye içinde Transfermarkt üzerinden istediği takımı seçer.
3. **3.. 2.. 1.. Başla!** Takımlar eşleşir ve ekranda açılır (Örn: *Arsenal FC ⚔️ Chelsea FC*).
4. **Hızlı Yazan Kazanır:** Ortak futbolculardan birini (Örn: *Didier Drogba, Petr Cech, Nicolas Anelka*) ilk yazan raundun puanını alır!
5. **Hedef Puan:** 3 (veya 5) puana ilk ulaşan şampiyon olur.

---

## 🚀 Yerel Geliştirme (Local Run)

### 1. Web Uygulamasını Çalıştırma (Tek Komut)

Tüm backend (FastAPI, WebSockets) ve React frontend arayüzünü tek komutla ayağa kaldırın:

```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Sunucuyu başlatın
python -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000
```
Tarayıcınızda açın: **[http://localhost:8000](http://localhost:8000)**

*(Frontend'i React Hot-Reload ile geliştirmek isterseniz `cd frontend && npm run dev` komutunu da kullanabilirsiniz).*

---

### 2. Lig Verisi Tarama (League Scraper)

İstediğiniz ligdeki tüm takımların transfer arşivlerini indirip oyuna gömmek için:

```bash
python league_scraper.py --league TR1  # Süper Lig
python league_scraper.py --league GB1  # Premier League
python league_scraper.py --league ES1  # LaLiga
```

---

### 3. Terminal Oyunu (CLI Versiyonu)

Web arayüzü yerine doğrudan terminalde oynamak veya `.exe` dosyasını kullanmak için:

```bash
cd terminal_app
python main.py
# veya dist/common_player.exe dosyasını çift tıklayarak çalıştırın.
```

---

## ☁️ Railway Deployment

Bu proje Railway üzerinde sıfır konfigürasyonla çalışmaya hazırdır:

1. Bu depoyu GitHub hesabınıza push edin.
2. [Railway.app](https://railway.app)'e girin ve **"New Project" -> "Deploy from GitHub repo"** seçin.
3. Railway `Procfile` ve `requirements.txt` dosyalarını otomatik algılayarak FastAPI sunucusunu ve gömülü verileri ayağa kaldıracaktır.
4. Railway Settings sekmesinden **"Generate Domain"** diyerek canlı linkinizi (örn: `https://common-player-game.up.railway.app`) anında alabilirsiniz!
