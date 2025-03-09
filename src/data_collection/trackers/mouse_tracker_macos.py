"""
MacOS fare izleyicisi.

Bu modül, MacOS'ta fare aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
import threading
import Quartz
import AppKit
from pynput import mouse
from .base_tracker import BaseTracker
from ..config import ENABLE_MOUSE_TRACKING, EXCLUDED_APPS, COLLECTION_INTERVAL
from ..database import MouseActivity

logger = logging.getLogger(__name__)

class MouseTrackerMacOS(BaseTracker):
    """MacOS'ta fare aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.click_count = 0
        self.move_count = 0
        self.scroll_count = 0
        self.last_activity_time = None
        self.lock = threading.Lock()
        self.listener = None
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_MOUSE_TRACKING:
            self.logger.info("Fare izleme devre dışı bırakıldı")
            self.stop()
            return
        
        # Fare dinleyicisini başlat
        try:
            self.listener = mouse.Listener(
                on_move=self._on_move,
                on_click=self._on_click,
                on_scroll=self._on_scroll
            )
            self.listener.daemon = True  # Daemon thread olarak ayarla
            self.listener.start()
            self.last_activity_time = datetime.datetime.now()
        except Exception as e:
            self.logger.error(f"Fare dinleyicisi başlatılırken hata oluştu: {e}")
            self.listener = None
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_MOUSE_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        time_diff = (current_time - self.last_activity_time).total_seconds()
        
        # Belirli bir süre geçtiyse ve fare aktivitesi varsa, aktiviteyi kaydet
        if time_diff >= COLLECTION_INTERVAL and (self.click_count > 0 or self.move_count > 0 or self.scroll_count > 0):
            with self.lock:
                # Aktif pencere bilgilerini al
                window_info = self._get_active_window_info()
                if window_info:
                    app_name = window_info['application_name'].lower()
                    # Hariç tutulan uygulamaları kontrol et
                    if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                        try:
                            # Veritabanına kaydet
                            mouse_activity = MouseActivity(
                                session_id=self.session_id,
                                timestamp=self.last_activity_time,
                                window_title=window_info['window_title'],
                                application_name=window_info['application_name'],
                                click_count=self.click_count,
                                move_count=self.move_count,
                                scroll_count=self.scroll_count,
                                duration=int(time_diff)
                            )
                            self.db_session.add(mouse_activity)
                            self.db_session.commit()
                            self.logger.info(f"Fare aktivitesi tespit edildi: {window_info['application_name']} - {self.click_count} tıklama, {self.move_count} hareket, {self.scroll_count} kaydırma ({int(time_diff)}s)")
                        except Exception as e:
                            self.logger.error(f"Fare aktivitesi kaydedilirken hata oluştu: {e}")
                            self.db_session.rollback()
                
                # Sayaçları sıfırla
                self.click_count = 0
                self.move_count = 0
                self.scroll_count = 0
                self.last_activity_time = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son aktiviteyi kaydet
        if self.click_count > 0 or self.move_count > 0 or self.scroll_count > 0:
            current_time = datetime.datetime.now()
            time_diff = (current_time - self.last_activity_time).total_seconds()
            
            # Aktif pencere bilgilerini al
            window_info = self._get_active_window_info()
            if window_info:
                app_name = window_info['application_name'].lower()
                # Hariç tutulan uygulamaları kontrol et
                if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                    try:
                        # Veritabanına kaydet
                        mouse_activity = MouseActivity(
                            session_id=self.session_id,
                            timestamp=self.last_activity_time,
                            window_title=window_info['window_title'],
                            application_name=window_info['application_name'],
                            click_count=self.click_count,
                            move_count=self.move_count,
                            scroll_count=self.scroll_count,
                            duration=int(time_diff)
                        )
                        self.db_session.add(mouse_activity)
                        self.db_session.commit()
                        self.logger.info(f"Son fare aktivitesi kaydedildi: {window_info['application_name']} - {self.click_count} tıklama, {self.move_count} hareket, {self.scroll_count} kaydırma ({int(time_diff)}s)")
                    except Exception as e:
                        self.logger.error(f"Son fare aktivitesi kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
        
        # Fare dinleyicisini durdur
        if self.listener:
            try:
                self.listener.stop()
                # Thread join'i devre dışı bırak
                # self.listener.join()
            except Exception as e:
                self.logger.error(f"Fare dinleyicisi durdurulurken hata oluştu: {e}")
            self.listener = None
        
        self.click_count = 0
        self.move_count = 0
        self.scroll_count = 0
        self.last_activity_time = None
    
    def _on_move(self, x, y):
        """Fare hareket ettiğinde çağrılan fonksiyon.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
        """
        with self.lock:
            self.move_count += 1
    
    def _on_click(self, x, y, button, pressed):
        """Fare tıklandığında çağrılan fonksiyon.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
            button: Tıklanan düğme.
            pressed: Düğme basıldı mı?
        """
        if pressed:
            with self.lock:
                self.click_count += 1
    
    def _on_scroll(self, x, y, dx, dy):
        """Fare kaydırıldığında çağrılan fonksiyon.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
            dx: X yönündeki kaydırma miktarı.
            dy: Y yönündeki kaydırma miktarı.
        """
        with self.lock:
            self.scroll_count += 1
    
    def _get_active_window_info(self):
        """Aktif pencere bilgilerini al.
        
        Returns:
            dict: Pencere bilgileri (window_title, application_name) veya None.
        """
        try:
            # Aktif uygulamayı al
            active_app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
            if not active_app:
                return None
            
            # Uygulama adını al
            application_name = active_app.localizedName()
            if not application_name:
                return None
            
            # İşlem ID'sini al
            process_id = active_app.processIdentifier()
            
            # Aktif pencere başlığını al
            window_title = "Unknown"
            
            # Quartz ile tüm pencereleri al
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID
            )
            
            # Aktif uygulamanın pencerelerini bul
            for window in window_list:
                if window.get('kCGWindowOwnerPID', 0) == process_id:
                    # Pencere başlığını al
                    title = window.get('kCGWindowName', '')
                    if title:
                        window_title = title
                        break
            
            return {
                'window_title': window_title,
                'application_name': application_name,
                'process_id': process_id
            }
        except Exception as e:
            self.logger.error(f"Aktif pencere bilgileri alınırken hata oluştu: {e}")
            return None
    
    def get_activity_counts(self):
        """Aktivite sayılarını döndür.
        
        Returns:
            tuple: (click_count, move_count, scroll_count)
        """
        with self.lock:
            return (self.click_count, self.move_count, self.scroll_count) 