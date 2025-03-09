# Cursor: Otomatik Kişisel Aktivite Takipçisi ve İçerik Oluşturucu

Cursor, kişisel bilgisayarınızdaki (Windows/macOS) aktiviteleri otomatik olarak takip eden ve bu aktivitelere dayalı olarak yapay zeka ile anlamlı içerikler oluşturan bir sistemdir.

## Proje Bileşenleri

Proje üç ana bileşenden oluşmaktadır:

1. **Veri Toplama (Daemon/Servis Katmanı)**: Arka planda çalışan ve kullanıcı etkileşimlerini çeşitli kaynaklardan toplayan bir sistem servisi.
2. **Veri İşleme (Yapay Zeka Analiz Katmanı)**: Toplanan verileri analiz eden ve anlamlı özetler ve içgörüler oluşturan yapay zeka modelleri.
3. **İçerik Yayınlama (Web Entegrasyon Katmanı)**: İşlenen verileri biçimlendiren ve otomatik olarak kişisel bir web sitesine veya bloga yayınlayan modül.

## Kurulum

### Gereksinimler

- Python 3.9+
- Windows veya macOS işletim sistemi
- Windows için: pywin32
- macOS için: pyobjc (Cocoa ve Quartz framework'leri)

### Kurulum Adımları

1. Depoyu klonlayın:
   ```
   git clone https://github.com/kullanici/cursor-activity-tracker.git
   cd cursor-activity-tracker
   ```

2. Gerekli paketleri yükleyin:
   ```
   pip install -r requirements.txt
   ```

3. Ortam değişkenlerini ayarlayın:
   ```
   cp .env.example .env
   ```
   `.env` dosyasını düzenleyerek gerekli API anahtarlarını ve yapılandırma ayarlarını girin.

## Kullanım

### Veri Toplama Servisini Başlatma

Ana komut arayüzü üzerinden:
```
python src/main.py service start
```

Bu komut, işletim sisteminize göre uygun servisi/daemon'u otomatik olarak başlatacaktır.

Alternatif olarak, doğrudan servis/daemon modüllerini kullanabilirsiniz:

**Windows için:**
```
python src/main.py service install  # Servisi yükle
python src/main.py service start    # Servisi başlat
python src/main.py service stop     # Servisi durdur
python src/main.py service remove   # Servisi kaldır
```

**macOS için:**
```
python src/main.py service start    # Daemon'u başlat
python src/main.py service stop     # Daemon'u durdur
python src/main.py service restart  # Daemon'u yeniden başlat
```

### Veri İşleme ve İçerik Oluşturma

```
python src/main.py process --date YYYY-MM-DD
```

### İçerik Yayınlama

```
python src/main.py publish --date YYYY-MM-DD
```

## İzlenen Aktiviteler

Cursor aşağıdaki aktiviteleri izler:

- **Pencere Aktiviteleri**: Hangi uygulamaların ne kadar süre aktif olduğu
- **Klavye ve Fare Aktiviteleri**: Tuş basımları ve fare tıklamaları (içerik değil, sadece sayılar)
- **Dosya Sistemi Değişiklikleri**: Oluşturulan, değiştirilen ve silinen dosyalar
- **Tarayıcı Aktiviteleri**: Ziyaret edilen web siteleri (URL'ler)
- **Oyun Aktiviteleri**: Oynanan oyunlar ve süreleri

## MacOS Özellikleri

MacOS'ta Cursor aşağıdaki özellikleri kullanır:

- **AppKit ve Quartz**: Aktif pencere ve uygulama bilgilerini almak için
- **Watchdog**: Dosya sistemi değişikliklerini izlemek için
- **pynput**: Klavye ve fare aktivitelerini izlemek için
- **SQLite**: Tarayıcı geçmişi ve diğer verileri depolamak için

## Güvenlik ve Gizlilik

- Tüm veriler yerel olarak saklanır
- Hassas veriler filtrelenir ve kaydedilmez
- Kullanıcılar belirli uygulamalar için izlemeyi etkinleştirebilir veya devre dışı bırakabilir
- Klavye içeriği (basılan tuşlar) kaydedilmez, sadece tuş basım sayıları kaydedilir

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Daha fazla bilgi için `LICENSE` dosyasına bakın. 