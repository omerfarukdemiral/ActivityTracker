"""
Klavye izleyicisi.

Bu modül, klavye aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
from pynput import keyboard
from .base_tracker import BaseTracker
from .window_tracker import WindowTracker
from ..config import COLLECTION_INTERVAL, ENABLE_KEYBOARD_TRACKING, EXCLUDED_APPS
from ..database import KeyboardActivity

logger = logging.getLogger(__name__)

class KeyboardTracker(BaseTracker):
    """Klavye aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.key_count = 0
        self.last_save_time = None
        self.keyboard_listener = None
        self.window_tracker = None
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_KEYBOARD_TRACKING:
            logger.info("Klavye izleme devre dışı bırakıldı")
            self.stop()
            return
        
        logger.info("Klavye izleyici hazırlanıyor")
        self.key_count = 0
        self.last_save_time = datetime.datetime.now()
        
        # Klavye dinleyicisini başlat
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()
        
        # Pencere izleyicisini oluştur (sadece referans için, başlatma)
        self.window_tracker = WindowTracker(self.session_id)
    
    def _on_key_press(self, key):
        """Tuş basma olayını işle.
        
        Args:
            key: Basılan tuş.
        """
        if not self.is_running:
            return
        
        # Tuş sayısını artır
        self.key_count += 1
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_KEYBOARD_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        elapsed_seconds = (current_time - self.last_save_time).total_seconds()
        
        # Belirli aralıklarla veritabanına kaydet (10 saniye veya 10+ tuş vuruşu)
        if elapsed_seconds >= 10 or self.key_count >= 10:
            if self.key_count > 0:
                try:
                    # Aktif pencere ID'sini al (eğer varsa)
                    window_id = None
                    if self.window_tracker:
                        window_id = self.window_tracker.get_last_window_id()
                    
                    # Veritabanına kaydet
                    keyboard_activity = KeyboardActivity(
                        session_id=self.session_id,
                        timestamp=self.last_save_time,
                        key_count=self.key_count,
                        window_id=window_id
                    )
                    self.db_session.add(keyboard_activity)
                    self.db_session.commit()
                    logger.debug(f"Klavye aktivitesi kaydedildi: {self.key_count} tuş")
                except Exception as e:
                    logger.error(f"Klavye aktivitesi kaydedilirken hata oluştu: {e}")
                    self.db_session.rollback()
            
            # Sayaçları sıfırla
            self.key_count = 0
            self.last_save_time = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son tuş vuruşlarını kaydet
        if self.key_count > 0:
            try:
                # Aktif pencere ID'sini al (eğer varsa)
                window_id = None
                if self.window_tracker:
                    window_id = self.window_tracker.get_last_window_id()
                
                # Veritabanına kaydet
                keyboard_activity = KeyboardActivity(
                    session_id=self.session_id,
                    timestamp=self.last_save_time,
                    key_count=self.key_count,
                    window_id=window_id
                )
                self.db_session.add(keyboard_activity)
                self.db_session.commit()
                logger.debug(f"Son klavye aktivitesi kaydedildi: {self.key_count} tuş")
            except Exception as e:
                logger.error(f"Son klavye aktivitesi kaydedilirken hata oluştu: {e}")
                self.db_session.rollback()
        
        # Klavye dinleyicisini durdur
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        
        self.key_count = 0
        self.last_save_time = None
        logger.info("Klavye izleyici temizlendi") 