"""
Tarayıcı aktivitelerini kontrol etme betiği.

Bu betik, veritabanındaki tarayıcı aktivitelerini kontrol eder.
"""
import os
import sys
import logging
import datetime
from data_collection.database import get_session, BrowserActivity, ActivitySession

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Ana fonksiyon."""
    logger.info("Tarayıcı aktivitelerini kontrol etme betiği başlatılıyor...")
    
    # Veritabanı oturumu oluştur
    db_session = get_session()
    try:
        # Tüm aktivite oturumlarını al
        sessions = db_session.query(ActivitySession).all()
        logger.info(f"Toplam {len(sessions)} aktivite oturumu bulundu.")
        
        for session in sessions:
            logger.info(f"Oturum ID: {session.id}, Başlangıç: {session.start_time}, Bitiş: {session.end_time}, Aktif: {session.is_active}")
            
            # Oturumdaki tarayıcı aktivitelerini al
            browser_activities = db_session.query(BrowserActivity).filter_by(session_id=session.id).all()
            logger.info(f"  Oturumda {len(browser_activities)} tarayıcı aktivitesi bulundu.")
            
            for activity in browser_activities:
                logger.info(f"  - URL: {activity.url}")
                logger.info(f"    Başlık: {activity.title}")
                logger.info(f"    Alan Adı: {activity.domain}")
                logger.info(f"    Süre: {activity.duration} saniye")
                logger.info(f"    Zaman: {activity.timestamp}")
                logger.info(f"    Pencere ID: {activity.window_id}")
                logger.info("  ---")
    except Exception as e:
        logger.error(f"Tarayıcı aktiviteleri kontrol edilirken hata oluştu: {e}")
    finally:
        db_session.close()
    
    logger.info("Tarayıcı aktiviteleri kontrol edildi.")

if __name__ == '__main__':
    main() 