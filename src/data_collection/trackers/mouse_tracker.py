"""
Fare izleyicisi.

Bu modül, fare aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
import math
from pynput import mouse
from .base_tracker import BaseTracker
from .window_tracker import WindowTracker
from ..config import COLLECTION_INTERVAL, ENABLE_MOUSE_TRACKING
from ..database import MouseActivity

logger = logging.getLogger(__name__)

class MouseTracker(BaseTracker):
    """Fare aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.click_count = 0
        self.movement_pixels = 0
        self.last_position = None
        self.last_save_time = None
        self.mouse_listener = None
        self.window_tracker = None
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_MOUSE_TRACKING:
            logger.info("Fare izleme devre dışı bırakıldı")
            self.stop()
            return
        
        logger.info("Fare izleyici hazırlanıyor")
        self.click_count = 0
        self.movement_pixels = 0
        self.last_position = None
        self.last_save_time = datetime.datetime.now()
        
        # Fare dinleyicisini başlat
        self.mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click
        )
        self.mouse_listener.start()
        
        # Pencere izleyicisini oluştur (sadece referans için, başlatma)
        self.window_tracker = WindowTracker(self.session_id)
    
    def _on_move(self, x, y):
        """Fare hareket olayını işle.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
        """
        if not self.is_running:
            return
        
        # İlk konum ise kaydet ve çık
        if self.last_position is None:
            self.last_position = (x, y)
            return
        
        # Hareket mesafesini hesapla (Öklid mesafesi)
        distance = math.sqrt((x - self.last_position[0])**2 + (y - self.last_position[1])**2)
        self.movement_pixels += int(distance)
        self.last_position = (x, y)
    
    def _on_click(self, x, y, button, pressed):
        """Fare tıklama olayını işle.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
            button: Tıklanan düğme.
            pressed: Basıldı mı (True) yoksa bırakıldı mı (False).
        """
        if not self.is_running:
            return
        
        # Sadece basma olaylarını say
        if pressed:
            self.click_count += 1
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_MOUSE_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        elapsed_seconds = (current_time - self.last_save_time).total_seconds()
        
        # Belirli aralıklarla veritabanına kaydet (10 saniye veya aktivite varsa)
        if elapsed_seconds >= 10 or self.click_count > 0 or self.movement_pixels > 100:
            if self.click_count > 0 or self.movement_pixels > 0:
                try:
                    # Aktif pencere ID'sini al (eğer varsa)
                    window_id = None
                    if self.window_tracker:
                        window_id = self.window_tracker.get_last_window_id()
                    
                    # Veritabanına kaydet
                    mouse_activity = MouseActivity(
                        session_id=self.session_id,
                        timestamp=self.last_save_time,
                        click_count=self.click_count,
                        movement_pixels=self.movement_pixels,
                        window_id=window_id
                    )
                    self.db_session.add(mouse_activity)
                    self.db_session.commit()
                    logger.debug(f"Fare aktivitesi kaydedildi: {self.click_count} tıklama, {self.movement_pixels} piksel hareket")
                except Exception as e:
                    logger.error(f"Fare aktivitesi kaydedilirken hata oluştu: {e}")
                    self.db_session.rollback()
            
            # Sayaçları sıfırla
            self.click_count = 0
            self.movement_pixels = 0
            self.last_save_time = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son fare aktivitelerini kaydet
        if self.click_count > 0 or self.movement_pixels > 0:
            try:
                # Aktif pencere ID'sini al (eğer varsa)
                window_id = None
                if self.window_tracker:
                    window_id = self.window_tracker.get_last_window_id()
                
                # Veritabanına kaydet
                mouse_activity = MouseActivity(
                    session_id=self.session_id,
                    timestamp=self.last_save_time,
                    click_count=self.click_count,
                    movement_pixels=self.movement_pixels,
                    window_id=window_id
                )
                self.db_session.add(mouse_activity)
                self.db_session.commit()
                logger.debug(f"Son fare aktivitesi kaydedildi: {self.click_count} tıklama, {self.movement_pixels} piksel hareket")
            except Exception as e:
                logger.error(f"Son fare aktivitesi kaydedilirken hata oluştu: {e}")
                self.db_session.rollback()
        
        # Fare dinleyicisini durdur
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        
        self.click_count = 0
        self.movement_pixels = 0
        self.last_position = None
        self.last_save_time = None
        logger.info("Fare izleyici temizlendi") 