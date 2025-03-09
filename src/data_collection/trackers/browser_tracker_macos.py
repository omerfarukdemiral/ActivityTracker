"""
MacOS tarayıcı izleyicisi.

Bu modül, MacOS'ta tarayıcı aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import os
import time
import logging
import datetime
import sqlite3
import threading
import shutil
import tempfile
import Quartz
import AppKit
from pathlib import Path
from .base_tracker import BaseTracker
from ..config import ENABLE_BROWSER_TRACKING, EXCLUDED_APPS, COLLECTION_INTERVAL
from ..database import BrowserActivity

logger = logging.getLogger(__name__)

# MacOS'ta tarayıcı veritabanı yolları
BROWSER_DB_PATHS = {
    'chrome': '~/Library/Application Support/Google/Chrome/Default/History',
    'safari': '~/Library/Safari/History.db',
    'firefox': '~/Library/Application Support/Firefox/Profiles/*.default*/places.sqlite',
    'edge': '~/Library/Application Support/Microsoft Edge/Default/History',
    'brave': '~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History',
    'opera': '~/Library/Application Support/com.operasoftware.Opera/History'
}

class BrowserTrackerMacOS(BaseTracker):
    """MacOS'ta tarayıcı aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.last_activity_time = None
        self.lock = threading.Lock()
        self.browser_histories = {}
        self.last_urls = {}
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_BROWSER_TRACKING:
            self.logger.info("Tarayıcı izleme devre dışı bırakıldı")
            self.stop()
            return
        
        # Tarayıcı veritabanlarını kontrol et
        for browser, db_path in BROWSER_DB_PATHS.items():
            expanded_path = os.path.expanduser(db_path)
            # Glob pattern varsa
            if '*' in expanded_path:
                import glob
                paths = glob.glob(expanded_path)
                if paths:
                    self.browser_histories[browser] = {
                        'path': paths[0],
                        'last_timestamp': 0
                    }
                    self.logger.info(f"{browser.capitalize()} tarayıcısı bulundu: {paths[0]}")
            else:
                if os.path.exists(expanded_path):
                    self.browser_histories[browser] = {
                        'path': expanded_path,
                        'last_timestamp': 0
                    }
                    self.logger.info(f"{browser.capitalize()} tarayıcısı bulundu: {expanded_path}")
        
        if not self.browser_histories:
            self.logger.warning("Hiçbir tarayıcı veritabanı bulunamadı")
        
        self.last_activity_time = datetime.datetime.now()
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_BROWSER_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        time_diff = (current_time - self.last_activity_time).total_seconds()
        
        # Belirli bir süre geçtiyse, tarayıcı geçmişini kontrol et
        if time_diff >= COLLECTION_INTERVAL:
            with self.lock:
                # Aktif pencere bilgilerini al
                window_info = self._get_active_window_info()
                
                # Her tarayıcı için geçmişi kontrol et
                for browser, info in self.browser_histories.items():
                    try:
                        # Tarayıcı veritabanını kopyala (kilitlenme sorunlarını önlemek için)
                        temp_db = self._copy_db_to_temp(info['path'])
                        if not temp_db:
                            continue
                        
                        # Yeni URL'leri al
                        new_urls = self._get_new_browser_history(browser, temp_db, info['last_timestamp'])
                        
                        # Geçici veritabanını temizle
                        try:
                            os.remove(temp_db)
                        except:
                            pass
                        
                        if new_urls:
                            # Son zaman damgasını güncelle
                            info['last_timestamp'] = max(url['timestamp'] for url in new_urls)
                            
                            # URL'leri grupla (domain bazında)
                            grouped_urls = {}
                            for url_info in new_urls:
                                domain = self._extract_domain(url_info['url'])
                                if domain not in grouped_urls:
                                    grouped_urls[domain] = {
                                        'domain': domain,
                                        'count': 0,
                                        'urls': []
                                    }
                                
                                grouped_urls[domain]['count'] += 1
                                grouped_urls[domain]['urls'].append(url_info['url'])
                            
                            # Grupları veritabanına kaydet
                            for domain, group_data in grouped_urls.items():
                                try:
                                    # Veritabanına kaydet
                                    browser_activity = BrowserActivity(
                                        session_id=self.session_id,
                                        timestamp=self.last_activity_time,
                                        browser_name=browser,
                                        domain=domain,
                                        url_count=group_data['count'],
                                        url_list=','.join(group_data['urls'][:10]),  # İlk 10 URL'yi kaydet
                                        duration=int(time_diff)
                                    )
                                    self.db_session.add(browser_activity)
                                    self.db_session.commit()
                                    self.logger.info(f"Tarayıcı aktivitesi tespit edildi: {browser} - {domain} - {group_data['count']} URL ({int(time_diff)}s)")
                                except Exception as e:
                                    self.logger.error(f"Tarayıcı aktivitesi kaydedilirken hata oluştu: {e}")
                                    self.db_session.rollback()
                    except Exception as e:
                        self.logger.error(f"{browser} tarayıcı geçmişi alınırken hata oluştu: {e}")
                
                self.last_activity_time = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        self.browser_histories = {}
        self.last_urls = {}
        self.last_activity_time = None
    
    def _copy_db_to_temp(self, db_path):
        """Veritabanını geçici bir konuma kopyala.
        
        Args:
            db_path: Veritabanı yolu.
            
        Returns:
            str: Geçici veritabanı yolu veya None.
        """
        try:
            temp_dir = tempfile.gettempdir()
            temp_db = os.path.join(temp_dir, f"browser_history_{os.getpid()}.db")
            shutil.copy2(db_path, temp_db)
            return temp_db
        except Exception as e:
            self.logger.error(f"Veritabanı kopyalanırken hata oluştu: {e}")
            return None
    
    def _get_new_browser_history(self, browser, db_path, last_timestamp):
        """Tarayıcı geçmişinden yeni URL'leri al.
        
        Args:
            browser: Tarayıcı adı.
            db_path: Veritabanı yolu.
            last_timestamp: Son zaman damgası.
            
        Returns:
            list: Yeni URL'ler.
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if browser == 'chrome' or browser == 'edge' or browser == 'brave' or browser == 'opera':
                # Chrome/Edge/Brave/Opera için sorgu
                query = """
                SELECT url, title, last_visit_time/1000000-11644473600 as visit_time
                FROM urls
                WHERE last_visit_time/1000000-11644473600 > ?
                ORDER BY last_visit_time DESC
                LIMIT 100
                """
                cursor.execute(query, (last_timestamp,))
                
                results = []
                for url, title, visit_time in cursor.fetchall():
                    results.append({
                        'url': url,
                        'title': title,
                        'timestamp': visit_time
                    })
                
                conn.close()
                return results
            
            elif browser == 'firefox':
                # Firefox için sorgu
                query = """
                SELECT p.url, p.title, h.visit_date/1000000 as visit_time
                FROM moz_places p
                JOIN moz_historyvisits h ON p.id = h.place_id
                WHERE h.visit_date/1000000 > ?
                ORDER BY h.visit_date DESC
                LIMIT 100
                """
                cursor.execute(query, (last_timestamp,))
                
                results = []
                for url, title, visit_time in cursor.fetchall():
                    results.append({
                        'url': url,
                        'title': title,
                        'timestamp': visit_time
                    })
                
                conn.close()
                return results
            
            elif browser == 'safari':
                # Safari için sorgu
                query = """
                SELECT url, title, visit_time
                FROM history_visits v
                JOIN history_items i ON v.history_item = i.id
                WHERE visit_time > ?
                ORDER BY visit_time DESC
                LIMIT 100
                """
                cursor.execute(query, (last_timestamp,))
                
                results = []
                for url, title, visit_time in cursor.fetchall():
                    results.append({
                        'url': url,
                        'title': title,
                        'timestamp': visit_time
                    })
                
                conn.close()
                return results
            
            else:
                conn.close()
                return []
        
        except Exception as e:
            self.logger.error(f"Tarayıcı geçmişi alınırken hata oluştu: {e}")
            return []
    
    def _extract_domain(self, url):
        """URL'den domain adını çıkar.
        
        Args:
            url: URL.
            
        Returns:
            str: Domain adı.
        """
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return url
    
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