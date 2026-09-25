# ⚽ Ortak Oyuncu Bulucu (Terminal & Masaüstü Uygulaması)

İki futbol kulübü arasındaki geçmişten günümüze tüm ortak oyuncuları Transfermarkt üzerinden listeleyen ve oyuncu araması yapmanızı sağlayan terminal aracı.

---

## 🚀 Çalıştırma

### 1. Python ile Çalıştırma:
```powershell
python main.py
```

### 2. Hazır Exe ile Çalıştırma:
`dist/common_player.exe` dosyasına çift tıklayarak doğrudan çalıştırabilirsiniz (Python gerektirmez).

### 3. Yeni Exe Derleme (Kendi İkonunuzla):
İstediğiniz `.ico` dosyasını bu klasöre koyup şu komutu çalıştırabilirsiniz:
```powershell
pyinstaller --onefile --name "common_player" --icon="icon.ico" --clean --collect-all rich --collect-all bs4 main.py
```

---

## 📁 Dosya Yapısı

- `main.py`: Terminal uygulamasının ana akışı ve menüsü
- `ui.py`: Rich kütüphanesiyle hazırlanan renkli arayüz, tablolar ve kartlar
- `scraper.py`: Transfermarkt kulüp arama, transfer geçmişi ve oyuncu profil çekme motoru
- `comparator.py`: Benzersiz Transfermarkt ID eşleştirme ve harf toleranslı arama motoru
- `cache_manager.py`: Çekilen kulüp verilerini yerel `.cache` klasöründe saklayan önbellek yöneticisi
- `icon.ico` & `create_icon.py`: Uygulama simgesi ve ikon üretim kodu
- `dist/`: Derlenmiş bağımsız `common_player.exe` dosyası
