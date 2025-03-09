"""
Dosya izleyicisi.

Bu modül, dosya sistemi değişikliklerini izlemek ve kaydetmek için kullanılır.
"""
import os
import time
import logging
import datetime
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .base_tracker import BaseTracker
from .window_tracker import WindowTracker
from ..config import COLLECTION_INTERVAL, ENABLE_FILE_TRACKING, EXCLUDED_DIRECTORIES, DATABASE_PATH
from ..database import FileActivity

logger = logging.getLogger(__name__)

class FileEventHandler(FileSystemEventHandler):
    """Dosya sistemi olaylarını işleyen sınıf."""
    
    def __init__(self, tracker):
        """İşleyiciyi başlat.
        
        Args:
            tracker: Dosya izleyici referansı.
        """
        self.tracker = tracker
    
    def on_created(self, event):
        """Dosya oluşturma olayını işle."""
        if event.is_directory:
            return
        self.tracker.add_file_event(event.src_path, "created")
    
    def on_modified(self, event):
        """Dosya değiştirme olayını işle."""
        if event.is_directory:
            return
        self.tracker.add_file_event(event.src_path, "modified")
    
    def on_deleted(self, event):
        """Dosya silme olayını işle."""
        if event.is_directory:
            return
        self.tracker.add_file_event(event.src_path, "deleted")
    
    def on_moved(self, event):
        """Dosya taşıma olayını işle."""
        if event.is_directory:
            return
        self.tracker.add_file_event(event.dest_path, "moved", src_path=event.src_path)

class FileTracker(BaseTracker):
    """Dosya sistemi değişikliklerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.observer = None
        self.event_handler = None
        self.file_events = []
        self.file_events_lock = threading.Lock()
        self.window_tracker = None
        
        # Proje dizini ve veritabanı dosyasını hariç tut
        self.project_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
        self.db_file_path = os.path.abspath(DATABASE_PATH)
        
        # İzlenecek dizinler
        self.watch_paths = self._get_watch_paths()
    
    def _get_watch_paths(self):
        """İzlenecek dizinleri belirle.
        
        Returns:
            list: İzlenecek dizinlerin listesi.
        """
        # Kullanıcı dizinini izle
        user_home = os.path.expanduser("~")
        
        # İzlenecek dizinler
        watch_paths = [
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Downloads")
        ]
        
        # Hariç tutulan dizinleri filtrele
        filtered_paths = []
        for path in watch_paths:
            if os.path.exists(path) and not any(path.startswith(excluded) for excluded in EXCLUDED_DIRECTORIES):
                # Proje dizini içinde değilse ekle
                if not os.path.commonpath([path, self.project_dir]) == self.project_dir:
                    filtered_paths.append(path)
        
        return filtered_paths
    
    def add_file_event(self, file_path, action, src_path=None):
        """Dosya olayını kaydet.
        
        Args:
            file_path: Dosya yolu.
            action: Olay türü (created, modified, deleted, moved).
            src_path: Taşıma olayı için kaynak yol.
        """
        # Mutlak dosya yolunu al
        abs_file_path = os.path.abspath(file_path)
        
        # Proje dizinini ve veritabanı dosyasını kontrol et
        if os.path.commonpath([abs_file_path, self.project_dir]) == self.project_dir:
            return
        
        # Veritabanı dosyasını kontrol et
        if abs_file_path == self.db_file_path or (
            os.path.dirname(abs_file_path) == os.path.dirname(self.db_file_path) and 
            abs_file_path.endswith('.db')
        ):
            return
        
        # Hariç tutulan dizinleri kontrol et
        if any(abs_file_path.startswith(excluded) for excluded in EXCLUDED_DIRECTORIES):
            return
        
        # Dosya uzantısını al
        _, file_extension = os.path.splitext(abs_file_path)
        file_extension = file_extension.lower().lstrip('.')
        
        with self.file_events_lock:
            self.file_events.append({
                'file_path': abs_file_path,
                'action': action,
                'src_path': src_path,
                'timestamp': datetime.datetime.now(),
                'file_type': file_extension
            })
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_FILE_TRACKING:
            self.logger.info("Dosya izleme devre dışı bırakıldı")
            self.stop()
            return
        
        self.logger.info(f"İzlenen dizinler: {', '.join(self.watch_paths)}")
        
        # Pencere izleyicisini oluştur (sadece referans için, başlatma)
        self.window_tracker = WindowTracker(self.session_id)
        
        # Dosya olayları listesini temizle
        with self.file_events_lock:
            self.file_events = []
        
        # Watchdog observer'ı başlat
        self.event_handler = FileEventHandler(self)
        self.observer = Observer()
        
        # İzlenecek dizinleri ekle
        for path in self.watch_paths:
            try:
                self.observer.schedule(self.event_handler, path, recursive=True)
            except Exception as e:
                self.logger.error(f"Dosya izleme başlatılırken hata oluştu ({path}): {e}")
        
        self.observer.start()
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_FILE_TRACKING:
            return
        
        # Dosya olaylarını işle
        with self.file_events_lock:
            if self.file_events:
                for event in self.file_events:
                    try:
                        # Aktif pencere ID'sini al (eğer varsa)
                        window_id = None
                        if self.window_tracker:
                            window_id = self.window_tracker.get_last_window_id()
                        
                        # Veritabanına kaydet
                        file_activity = FileActivity(
                            session_id=self.session_id,
                            timestamp=event['timestamp'],
                            file_path=event['file_path'],
                            action=event['action'],
                            file_type=event['file_type'],
                            window_id=window_id
                        )
                        self.db_session.add(file_activity)
                        self.db_session.commit()
                        
                        # Dosya yolunu kısalt
                        short_path = os.path.basename(event['file_path'])
                        self.logger.info(f"Aktivite tespit edildi: {event['action']} - {short_path}")
                    except Exception as e:
                        self.logger.error(f"Aktivite kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
                
                # Olayları temizle
                self.file_events = []
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son dosya olaylarını kaydet
        with self.file_events_lock:
            if self.file_events:
                for event in self.file_events:
                    try:
                        # Aktif pencere ID'sini al (eğer varsa)
                        window_id = None
                        if self.window_tracker:
                            window_id = self.window_tracker.get_last_window_id()
                        
                        # Veritabanına kaydet
                        file_activity = FileActivity(
                            session_id=self.session_id,
                            timestamp=event['timestamp'],
                            file_path=event['file_path'],
                            action=event['action'],
                            file_type=event['file_type'],
                            window_id=window_id
                        )
                        self.db_session.add(file_activity)
                        self.db_session.commit()
                        
                        # Dosya yolunu kısalt
                        short_path = os.path.basename(event['file_path'])
                        self.logger.info(f"Son aktivite kaydedildi: {event['action']} - {short_path}")
                    except Exception as e:
                        self.logger.error(f"Son aktivite kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
                
                # Olayları temizle
                self.file_events = []
        
        # Observer'ı durdur
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.observer = None
        
        self.event_handler = None 