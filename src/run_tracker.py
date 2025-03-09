"""
Cursor Aktivite Takipçisi Çalıştırma Betiği.

Bu betik, servisi yüklemeden doğrudan çalıştırır.
"""
import os
import sys
import time
import logging
import datetime
import threading
from data_collection.trackers.window_tracker import WindowTracker
from data_collection.trackers.keyboard_tracker import KeyboardTracker
from data_collection.trackers.mouse_tracker import MouseTracker
from data_collection.trackers.file_tracker import FileTracker
from data_collection.trackers.browser_tracker import BrowserTracker
from data_collection.trackers.game_tracker import GameTracker
from data_collection.database import get_session, ActivitySession
from data_collection.config import DATABASE_PATH

# Logging yapılandırması
logging.basicConfig(
    level=logging.WARNING,  # Genel log seviyesini WARNING olarak ayarla
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Ana logger'ı INFO seviyesine ayarla
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Tracker'lar için özel log seviyelerini ayarla
tracker_logger = logging.getLogger('data_collection.trackers')
tracker_logger.setLevel(logging.INFO)

def main():
    """Ana fonksiyon."""
    logger.info("Cursor Aktivite Takipçisi başlatılıyor...")
    
    # Veritabanı dizininin varlığını kontrol et
    db_dir = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Veritabanı dizini oluşturuldu: {db_dir}")
    
    logger.info(f"Veritabanı dosyası: {os.path.abspath(DATABASE_PATH)}")
    
    # Yeni bir aktivite oturumu oluştur
    db_session = get_session()
    try:
        session = ActivitySession()
        db_session.add(session)
        db_session.commit()
        logger.info(f"Aktivite oturumu oluşturuldu (ID: {session.id})")
    except Exception as e:
        logger.error(f"Oturum oluşturulurken hata oluştu: {e}")
        db_session.rollback()
        return
    finally:
        db_session.close()
    
    # İzleyicileri başlat
    trackers = [
        WindowTracker(session.id),
        KeyboardTracker(session.id),
        MouseTracker(session.id),
        FileTracker(session.id),
        BrowserTracker(session.id),
        GameTracker(session.id)
    ]
    
    for tracker in trackers:
        try:
            tracker.start()
        except Exception as e:
            logger.error(f"{tracker.__class__.__name__} başlatılırken hata oluştu: {e}")
    
    try:
        # Ana program çalışırken bekle
        logger.info("Aktivite takibi başladı. Durdurmak için Ctrl+C tuşlarına basın.")
        logger.info(f"Proje dizini: {os.path.abspath(os.path.dirname(__file__))}")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Çalışma sırasında hata oluştu: {e}")
    finally:
        # İzleyicileri durdur
        for tracker in trackers:
            try:
                tracker.stop()
            except Exception as e:
                logger.error(f"{tracker.__class__.__name__} durdurulurken hata oluştu: {e}")
        
        # Oturumu kapat
        db_session = get_session()
        try:
            activity_session = db_session.query(ActivitySession).filter_by(id=session.id).first()
            if activity_session:
                activity_session.end_time = datetime.datetime.now()
                activity_session.is_active = False
                db_session.commit()
                logger.info(f"Aktivite oturumu kapatıldı (ID: {activity_session.id})")
        except Exception as e:
            logger.error(f"Oturum kapatılırken hata oluştu: {e}")
            db_session.rollback()
        finally:
            db_session.close()
        
        logger.info("Cursor Aktivite Takipçisi durduruldu.")

if __name__ == '__main__':
    main() 