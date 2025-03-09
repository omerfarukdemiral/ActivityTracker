"""
MacOS pencere izleyicisi.

Bu modül, MacOS'ta aktif pencereleri izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
import psutil
import Quartz
import AppKit
from .base_tracker import BaseTracker
from ..config import COLLECTION_INTERVAL, ENABLE_WINDOW_TRACKING, EXCLUDED_APPS
from ..database import WindowActivity

logger = logging.getLogger(__name__)

class WindowTrackerMacOS(BaseTracker):
    """MacOS'ta aktif pencereleri izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.current_window = None
        self.current_window_start_time = None
        self.last_window_id = None
        self.active_windows = {}  # Aktif pencereleri ve başlangıç zamanlarını tutan sözlük
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_WINDOW_TRACKING:
            self.logger.info("Pencere izleme devre dışı bırakıldı")
            self.stop()
            return
        
        self.current_window = self._get_active_window_info()
        if self.current_window:
            self.current_window_start_time = datetime.datetime.now()
            # Aktif pencereyi sözlüğe ekle
            window_key = f"{self.current_window['application_name']}:{self.current_window['window_title']}"
            self.active_windows[window_key] = {
                'window': self.current_window,
                'start_time': self.current_window_start_time,
                'is_active': True
            }
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_WINDOW_TRACKING:
            return
        
        # Aktif pencereyi al
        window_info = self._get_active_window_info()
        current_time = datetime.datetime.now()
        
        # Pencere değiştiyse, önceki pencere için süreyi kaydet
        if self.current_window and window_info and (
            window_info['window_title'] != self.current_window['window_title'] or
            window_info['application_name'] != self.current_window['application_name']
        ):
            # Önceki pencere için süreyi hesapla
            duration_seconds = int((current_time - self.current_window_start_time).total_seconds())
            
            # Minimum süre kontrolü (1 saniyeden fazla ise kaydet)
            if duration_seconds > 1:
                # Hariç tutulan uygulamaları kontrol et
                app_name = self.current_window['application_name'].lower()
                if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                    try:
                        # Veritabanına kaydet
                        window_activity = WindowActivity(
                            session_id=self.session_id,
                            timestamp=self.current_window_start_time,
                            window_title=self.current_window['window_title'],
                            application_name=self.current_window['application_name'],
                            process_id=self.current_window['process_id'],
                            duration=duration_seconds
                        )
                        self.db_session.add(window_activity)
                        self.db_session.commit()
                        self.last_window_id = window_activity.id
                        self.logger.info(f"Aktivite tespit edildi: {self.current_window['application_name']} - {self.current_window['window_title']} ({duration_seconds}s)")
                    except Exception as e:
                        self.logger.error(f"Aktivite kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
            
            # Önceki pencereyi aktif olmayan olarak işaretle
            if self.current_window:
                window_key = f"{self.current_window['application_name']}:{self.current_window['window_title']}"
                if window_key in self.active_windows:
                    self.active_windows[window_key]['is_active'] = False
            
            # Yeni pencereyi ayarla
            self.current_window = window_info
            self.current_window_start_time = current_time
            
            # Yeni pencereyi aktif pencereler sözlüğüne ekle veya güncelle
            if window_info:
                window_key = f"{window_info['application_name']}:{window_info['window_title']}"
                if window_key in self.active_windows:
                    # Eğer daha önce bu pencere açıldıysa, sadece aktif durumunu güncelle
                    self.active_windows[window_key]['is_active'] = True
                else:
                    # Yeni pencere ise, sözlüğe ekle
                    self.active_windows[window_key] = {
                        'window': window_info,
                        'start_time': current_time,
                        'is_active': True
                    }
        
        # İlk kez pencere bilgisi alınıyorsa
        elif not self.current_window and window_info:
            self.current_window = window_info
            self.current_window_start_time = current_time
            
            # Yeni pencereyi aktif pencereler sözlüğüne ekle
            window_key = f"{window_info['application_name']}:{window_info['window_title']}"
            self.active_windows[window_key] = {
                'window': window_info,
                'start_time': current_time,
                'is_active': True
            }
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son aktif pencereyi kaydet
        if self.current_window:
            end_time = datetime.datetime.now()
            duration_seconds = int((end_time - self.current_window_start_time).total_seconds())
            
            if duration_seconds > 1:
                app_name = self.current_window['application_name'].lower()
                if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                    try:
                        window_activity = WindowActivity(
                            session_id=self.session_id,
                            timestamp=self.current_window_start_time,
                            window_title=self.current_window['window_title'],
                            application_name=self.current_window['application_name'],
                            process_id=self.current_window['process_id'],
                            duration=duration_seconds
                        )
                        self.db_session.add(window_activity)
                        self.db_session.commit()
                        self.logger.info(f"Son aktivite kaydedildi: {self.current_window['application_name']} - {self.current_window['window_title']} ({duration_seconds}s)")
                    except Exception as e:
                        self.logger.error(f"Son aktivite kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
        
        self.current_window = None
        self.current_window_start_time = None
        self.active_windows = {}
    
    def _get_active_window_info(self):
        """Aktif pencere bilgilerini al.
        
        Returns:
            dict: Pencere bilgileri (window_title, application_name, process_id) veya None.
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
    
    def get_last_window_id(self):
        """Son kaydedilen pencere ID'sini döndür.
        
        Returns:
            int: Son pencere ID'si veya None.
        """
        return self.last_window_id
    
    def get_active_window_duration(self, application_name, window_title):
        """Belirli bir pencerenin aktif olduğu toplam süreyi döndür.
        
        Args:
            application_name: Uygulama adı.
            window_title: Pencere başlığı.
            
        Returns:
            int: Toplam süre (saniye cinsinden) veya 0.
        """
        window_key = f"{application_name}:{window_title}"
        if window_key in self.active_windows:
            window_data = self.active_windows[window_key]
            if window_data['is_active']:
                # Eğer pencere hala aktifse, şu ana kadar geçen süreyi hesapla
                current_time = datetime.datetime.now()
                return int((current_time - window_data['start_time']).total_seconds())
        return 0 