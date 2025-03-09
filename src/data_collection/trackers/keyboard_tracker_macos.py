"""
MacOS klavye izleyicisi.

Bu modül, MacOS'ta klavye aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
import threading
import Quartz
import AppKit
from pynput import keyboard
from .base_tracker import BaseTracker
from ..config import ENABLE_KEYBOARD_TRACKING, EXCLUDED_APPS, COLLECTION_INTERVAL
from ..database import KeyboardActivity

logger = logging.getLogger(__name__)

class KeyboardTrackerMacOS(BaseTracker):
    """MacOS'ta klavye aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.key_count = 0
        self.last_activity_time = None
        self.lock = threading.Lock()
        self.listener = None
        self.window_tracker = None
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_KEYBOARD_TRACKING:
            self.logger.info("Klavye izleme devre dışı bırakıldı")
            self.stop()
            return
        
        # Klavye dinleyicisini başlat
        try:
            self.listener = keyboard.Listener(on_press=self._on_key_press)
            self.listener.daemon = True  # Daemon thread olarak ayarla
            self.listener.start()
            self.last_activity_time = datetime.datetime.now()
        except Exception as e:
            self.logger.error(f"Klavye dinleyicisi başlatılırken hata oluştu: {e}")
            self.listener = None
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_KEYBOARD_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        time_diff = (current_time - self.last_activity_time).total_seconds()
        
        # Belirli bir süre geçtiyse ve tuş basımı varsa, aktiviteyi kaydet
        if time_diff >= COLLECTION_INTERVAL and self.key_count > 0:
            with self.lock:
                # Aktif pencere bilgilerini al
                window_info = self._get_active_window_info()
                if window_info:
                    app_name = window_info['application_name'].lower()
                    # Hariç tutulan uygulamaları kontrol et
                    if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                        try:
                            # Veritabanına kaydet
                            keyboard_activity = KeyboardActivity(
                                session_id=self.session_id,
                                timestamp=self.last_activity_time,
                                window_title=window_info['window_title'],
                                application_name=window_info['application_name'],
                                key_count=self.key_count,
                                duration=int(time_diff)
                            )
                            self.db_session.add(keyboard_activity)
                            self.db_session.commit()
                            self.logger.info(f"Klavye aktivitesi tespit edildi: {window_info['application_name']} - {self.key_count} tuş ({int(time_diff)}s)")
                        except Exception as e:
                            self.logger.error(f"Klavye aktivitesi kaydedilirken hata oluştu: {e}")
                            self.db_session.rollback()
                
                # Sayacı sıfırla
                self.key_count = 0
                self.last_activity_time = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son aktiviteyi kaydet
        if self.key_count > 0:
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
                        keyboard_activity = KeyboardActivity(
                            session_id=self.session_id,
                            timestamp=self.last_activity_time,
                            window_title=window_info['window_title'],
                            application_name=window_info['application_name'],
                            key_count=self.key_count,
                            duration=int(time_diff)
                        )
                        self.db_session.add(keyboard_activity)
                        self.db_session.commit()
                        self.logger.info(f"Son klavye aktivitesi kaydedildi: {window_info['application_name']} - {self.key_count} tuş ({int(time_diff)}s)")
                    except Exception as e:
                        self.logger.error(f"Son klavye aktivitesi kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
        
        # Klavye dinleyicisini durdur
        if self.listener:
            try:
                self.listener.stop()
                # Thread join'i devre dışı bırak
                # self.listener.join()
            except Exception as e:
                self.logger.error(f"Klavye dinleyicisi durdurulurken hata oluştu: {e}")
            self.listener = None
        
        self.key_count = 0
        self.last_activity_time = None
    
    def _on_key_press(self, key):
        """Tuş basıldığında çağrılan fonksiyon.
        
        Args:
            key: Basılan tuş.
        """
        with self.lock:
            self.key_count += 1
    
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
    
    def get_key_count(self):
        """Tuş sayısını döndür.
        
        Returns:
            int: Tuş sayısı.
        """
        with self.lock:
            return self.key_count 