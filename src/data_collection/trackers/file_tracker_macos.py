"""
MacOS dosya izleyicisi.

Bu modül, MacOS'ta dosya sistemi değişikliklerini izlemek ve kaydetmek için kullanılır.
"""
import os
import time
import logging
import datetime
import threading
import Quartz
import AppKit
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .base_tracker import BaseTracker
from ..config import ENABLE_FILE_TRACKING, EXCLUDED_APPS, COLLECTION_INTERVAL, TRACKED_DIRECTORIES, EXCLUDED_DIRECTORIES, EXCLUDED_FILE_TYPES
from ..database import FileActivity

logger = logging.getLogger(__name__)

class FileEventHandler(FileSystemEventHandler):
    """Dosya sistemi olaylarını işleyen sınıf."""
    
    def __init__(self, tracker):
        """İşleyiciyi başlat.
        
        Args:
            tracker: Dosya izleyici.
        """
        self.tracker = tracker
    
    def on_created(self, event):
        """Dosya oluşturulduğunda çağrılan fonksiyon.
        
        Args:
            event: Olay.
        """
        if not event.is_directory:
            self.tracker.add_file_event('created', event.src_path)
    
    def on_deleted(self, event):
        """Dosya silindiğinde çağrılan fonksiyon.
        
        Args:
            event: Olay.
        """
        if not event.is_directory:
            self.tracker.add_file_event('deleted', event.src_path)
    
    def on_modified(self, event):
        """Dosya değiştirildiğinde çağrılan fonksiyon.
        
        Args:
            event: Olay.
        """
        if not event.is_directory:
            self.tracker.add_file_event('modified', event.src_path)
    
    def on_moved(self, event):
        """Dosya taşındığında çağrılan fonksiyon.
        
        Args:
            event: Olay.
        """
        if not event.is_directory:
            self.tracker.add_file_event('moved', event.dest_path, event.src_path)

class FileTrackerMacOS(BaseTracker):
    """MacOS'ta dosya sistemi değişikliklerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.observer = None
        self.file_events = []
        self.lock = threading.Lock()
        self.last_activity_time = None
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_FILE_TRACKING:
            self.logger.info("Dosya izleme devre dışı bırakıldı")
            self.stop()
            return
        
        # Dosya sistemi gözlemcisini başlat
        self.observer = Observer()
        event_handler = FileEventHandler(self)
        
        # İzlenecek dizinleri ekle
        for directory in TRACKED_DIRECTORIES:
            if os.path.exists(directory) and os.path.isdir(directory):
                self.observer.schedule(event_handler, directory, recursive=True)
                self.logger.info(f"Dizin izleniyor: {directory}")
            else:
                self.logger.warning(f"Dizin bulunamadı: {directory}")
        
        self.observer.start()
        self.last_activity_time = datetime.datetime.now()
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_FILE_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        time_diff = (current_time - self.last_activity_time).total_seconds()
        
        # Belirli bir süre geçtiyse ve dosya olayları varsa, aktiviteyi kaydet
        if time_diff >= COLLECTION_INTERVAL and len(self.file_events) > 0:
            with self.lock:
                # Aktif pencere bilgilerini al
                window_info = self._get_active_window_info()
                if window_info:
                    app_name = window_info['application_name'].lower()
                    # Hariç tutulan uygulamaları kontrol et
                    if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                        # Dosya olaylarını grupla
                        grouped_events = {}
                        for event in self.file_events:
                            event_type = event['event_type']
                            file_path = event['file_path']
                            
                            # Hariç tutulan dizinleri ve dosya türlerini kontrol et
                            if self._is_excluded_file(file_path):
                                continue
                            
                            # Dosya türünü al
                            file_ext = os.path.splitext(file_path)[1].lower()
                            
                            # Grupla
                            key = f"{event_type}:{file_ext}"
                            if key not in grouped_events:
                                grouped_events[key] = {
                                    'event_type': event_type,
                                    'file_extension': file_ext,
                                    'count': 0,
                                    'files': []
                                }
                            
                            grouped_events[key]['count'] += 1
                            grouped_events[key]['files'].append(file_path)
                        
                        # Grupları veritabanına kaydet
                        for group_key, group_data in grouped_events.items():
                            try:
                                # Veritabanına kaydet
                                file_activity = FileActivity(
                                    session_id=self.session_id,
                                    timestamp=self.last_activity_time,
                                    window_title=window_info['window_title'],
                                    application_name=window_info['application_name'],
                                    event_type=group_data['event_type'],
                                    file_extension=group_data['file_extension'],
                                    file_count=group_data['count'],
                                    file_list=','.join(group_data['files'][:10]),  # İlk 10 dosyayı kaydet
                                    duration=int(time_diff)
                                )
                                self.db_session.add(file_activity)
                                self.db_session.commit()
                                self.logger.info(f"Dosya aktivitesi tespit edildi: {window_info['application_name']} - {group_data['event_type']} - {group_data['file_extension']} - {group_data['count']} dosya ({int(time_diff)}s)")
                            except Exception as e:
                                self.logger.error(f"Dosya aktivitesi kaydedilirken hata oluştu: {e}")
                                self.db_session.rollback()
                
                # Dosya olaylarını temizle
                self.file_events = []
                self.last_activity_time = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son aktiviteyi kaydet
        if len(self.file_events) > 0:
            current_time = datetime.datetime.now()
            time_diff = (current_time - self.last_activity_time).total_seconds()
            
            # Aktif pencere bilgilerini al
            window_info = self._get_active_window_info()
            if window_info:
                app_name = window_info['application_name'].lower()
                # Hariç tutulan uygulamaları kontrol et
                if not any(excluded.lower() in app_name for excluded in EXCLUDED_APPS):
                    # Dosya olaylarını grupla
                    grouped_events = {}
                    for event in self.file_events:
                        event_type = event['event_type']
                        file_path = event['file_path']
                        
                        # Hariç tutulan dizinleri ve dosya türlerini kontrol et
                        if self._is_excluded_file(file_path):
                            continue
                        
                        # Dosya türünü al
                        file_ext = os.path.splitext(file_path)[1].lower()
                        
                        # Grupla
                        key = f"{event_type}:{file_ext}"
                        if key not in grouped_events:
                            grouped_events[key] = {
                                'event_type': event_type,
                                'file_extension': file_ext,
                                'count': 0,
                                'files': []
                            }
                        
                        grouped_events[key]['count'] += 1
                        grouped_events[key]['files'].append(file_path)
                    
                    # Grupları veritabanına kaydet
                    for group_key, group_data in grouped_events.items():
                        try:
                            # Veritabanına kaydet
                            file_activity = FileActivity(
                                session_id=self.session_id,
                                timestamp=self.last_activity_time,
                                window_title=window_info['window_title'],
                                application_name=window_info['application_name'],
                                event_type=group_data['event_type'],
                                file_extension=group_data['file_extension'],
                                file_count=group_data['count'],
                                file_list=','.join(group_data['files'][:10]),  # İlk 10 dosyayı kaydet
                                duration=int(time_diff)
                            )
                            self.db_session.add(file_activity)
                            self.db_session.commit()
                            self.logger.info(f"Son dosya aktivitesi kaydedildi: {window_info['application_name']} - {group_data['event_type']} - {group_data['file_extension']} - {group_data['count']} dosya ({int(time_diff)}s)")
                        except Exception as e:
                            self.logger.error(f"Son dosya aktivitesi kaydedilirken hata oluştu: {e}")
                            self.db_session.rollback()
        
        # Dosya sistemi gözlemcisini durdur
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.file_events = []
        self.last_activity_time = None
    
    def add_file_event(self, event_type, file_path, src_path=None):
        """Dosya olayı ekle.
        
        Args:
            event_type: Olay türü (created, deleted, modified, moved).
            file_path: Dosya yolu.
            src_path: Kaynak dosya yolu (taşıma olayları için).
        """
        with self.lock:
            self.file_events.append({
                'event_type': event_type,
                'file_path': file_path,
                'src_path': src_path,
                'timestamp': datetime.datetime.now()
            })
    
    def _is_excluded_file(self, file_path):
        """Dosyanın hariç tutulup tutulmadığını kontrol et.
        
        Args:
            file_path: Dosya yolu.
            
        Returns:
            bool: Dosya hariç tutuluyorsa True, aksi halde False.
        """
        # Hariç tutulan dizinleri kontrol et
        for excluded_dir in EXCLUDED_DIRECTORIES:
            if excluded_dir in file_path:
                return True
        
        # Hariç tutulan dosya türlerini kontrol et
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in EXCLUDED_FILE_TYPES:
            return True
        
        return False
    
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