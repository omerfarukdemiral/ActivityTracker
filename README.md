# Otomatik Kişisel Aktivite Takipçisi ve İçerik Oluşturucu

Kişisel bilgisayarınızdaki (Windows/macOS) aktiviteleri otomatik olarak takip eden ve bu aktivitelere dayalı olarak yapay zeka ile anlamlı içerikler oluşturan bir sistemdir.

## Proje Bileşenleri

Proje üç ana bileşenden oluşmaktadır:

1. **Veri Toplama (Daemon/Servis Katmanı)**: Arka planda çalışan ve kullanıcı etkileşimlerini çeşitli kaynaklardan toplayan bir sistem servisi.
2. **Veri İşleme (Yapay Zeka Analiz Katmanı)**: Toplanan verileri analiz eden ve anlamlı özetler ve içgörüler oluşturan yapay zeka modelleri.
3. **İçerik Yayınlama (Web Entegrasyon Katmanı)**: İşlenen verileri biçimlendiren ve otomatik olarak kişisel bir web sitesine veya bloga yayınlayan modül.

## Kurulum

### Gereksinimler

- Python 3.9+
- Windows veya macOS işletim sistemi

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

Windows için:
```
python src/data_collection/windows_service.py install
```

macOS için:
```
python src/data_collection/macos_daemon.py start
```

### Veri İşleme ve İçerik Oluşturma

```
python src/data_processing/process_data.py
```

### İçerik Yayınlama

```
python src/content_publishing/publish_content.py
```

## Güvenlik ve Gizlilik

- Tüm veriler yerel olarak saklanır
- Hassas veriler filtrelenir ve kaydedilmez
- Kullanıcılar belirli uygulamalar için izlemeyi etkinleştirebilir veya devre dışı bırakabilir

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Daha fazla bilgi için `LICENSE` dosyasına bakın. 
