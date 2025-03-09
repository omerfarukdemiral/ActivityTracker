"""
Tarayıcı izleyicisi.

Bu modül, web tarayıcı aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
import re
import urllib.parse
import os
import psutil
from .base_tracker import BaseTracker
from .window_tracker import WindowTracker
from ..config import COLLECTION_INTERVAL, ENABLE_BROWSER_TRACKING, EXCLUDED_WEBSITES
from ..database import BrowserActivity

logger = logging.getLogger(__name__)

class BrowserTracker(BaseTracker):
    """Web tarayıcı aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.current_url = None
        self.current_title = None
        self.current_domain = None
        self.current_start_time = None
        self.window_tracker = None
        self.active_tabs = {}  # Aktif sekmeleri ve başlangıç zamanlarını tutan sözlük
        
        # Desteklenen tarayıcılar
        self.browsers = [
            "chrome.exe",
            "firefox.exe",
            "msedge.exe",
            "opera.exe",
            "brave.exe",
            "safari.exe",
            "iexplore.exe",
            "chrome",
            "firefox",
            "msedge",
            "opera",
            "brave",
            "safari",
            "iexplore"
        ]
        
        # URL regex desenleri
        self.url_patterns = [
            r'https?://(?:www\.)?([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+)(?:/[^\s]*)?',  # Normal URL
            r'(?:www\.)?([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+)(?:/[^\s]*)?'  # www ile başlayan URL
        ]
        
        # Tarayıcı başlık desenleri
        self.browser_title_patterns = [
            r'(.+) - Google Chrome',
            r'(.+) - Mozilla Firefox',
            r'(.+) - Microsoft Edge',
            r'(.+) - Opera',
            r'(.+) - Brave',
            r'(.+) - Safari',
            r'(.+) - Internet Explorer',
            r'(.+) \| Google Chrome',
            r'(.+) \| Mozilla Firefox',
            r'(.+) \| Microsoft Edge',
            r'(.+) \| Opera',
            r'(.+) \| Brave',
            r'(.+) \| Safari',
            r'(.+) \| Internet Explorer'
        ]
        
        # Çalışan tarayıcıları kontrol et
        self._check_running_browsers()
    
    def _check_running_browsers(self):
        """Çalışan tarayıcıları kontrol et."""
        try:
            running_browsers = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    for browser in self.browsers:
                        if browser.lower() in proc_name:
                            running_browsers.append(proc_name)
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if running_browsers:
                self.logger.info(f"Çalışan tarayıcılar: {', '.join(set(running_browsers))}")
        except Exception as e:
            self.logger.error(f"Çalışan tarayıcılar kontrol edilirken hata oluştu: {e}")
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_BROWSER_TRACKING:
            self.logger.info("Tarayıcı izleme devre dışı bırakıldı")
            self.stop()
            return
        
        # Pencere izleyicisini oluştur (sadece referans için, başlatma)
        self.window_tracker = WindowTracker(self.session_id)
        
        # Mevcut URL bilgilerini temizle
        self.current_url = None
        self.current_title = None
        self.current_domain = None
        self.current_start_time = None
        self.active_tabs = {}
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_BROWSER_TRACKING:
            return
        
        # Aktif pencere bilgilerini al
        window_info = self._get_active_browser_window()
        current_time = datetime.datetime.now()
        
        if window_info:
            url = window_info.get('url')
            title = window_info.get('title')
            domain = window_info.get('domain')
            
            # URL değiştiyse, önceki URL için süreyi kaydet
            if self.current_url and url != self.current_url:
                # Önceki URL için süreyi hesapla
                duration_seconds = int((current_time - self.current_start_time).total_seconds())
                
                # Minimum süre kontrolü (3 saniyeden fazla ise kaydet)
                if duration_seconds > 3:
                    # Hariç tutulan web sitelerini kontrol et
                    if not self.current_domain or not any(excluded.lower() in self.current_domain.lower() for excluded in EXCLUDED_WEBSITES):
                        try:
                            # Aktif pencere ID'sini al (eğer varsa)
                            window_id = None
                            if self.window_tracker:
                                window_id = self.window_tracker.get_last_window_id()
                            
                            # Veritabanına kaydet
                            browser_activity = BrowserActivity(
                                session_id=self.session_id,
                                timestamp=self.current_start_time,
                                url=self.current_url,
                                title=self.current_title,
                                domain=self.current_domain,
                                duration=duration_seconds,
                                window_id=window_id
                            )
                            self.db_session.add(browser_activity)
                            self.db_session.commit()
                            self.logger.info(f"Aktivite tespit edildi: {self.current_domain} ({duration_seconds}s)")
                        except Exception as e:
                            self.logger.error(f"Aktivite kaydedilirken hata oluştu: {e}")
                            self.db_session.rollback()
                
                # Önceki sekmeyi aktif olmayan olarak işaretle
                if self.current_url and self.current_domain:
                    tab_key = f"{self.current_domain}:{self.current_url}"
                    if tab_key in self.active_tabs:
                        self.active_tabs[tab_key]['is_active'] = False
                
                # Yeni URL'yi ayarla
                self.current_url = url
                self.current_title = title
                self.current_domain = domain
                self.current_start_time = current_time
                
                # Yeni sekmeyi aktif sekmeler sözlüğüne ekle veya güncelle
                if url and domain:
                    tab_key = f"{domain}:{url}"
                    if tab_key in self.active_tabs:
                        # Eğer daha önce bu sekme açıldıysa, sadece aktif durumunu güncelle
                        self.active_tabs[tab_key]['is_active'] = True
                    else:
                        # Yeni sekme ise, sözlüğe ekle
                        self.active_tabs[tab_key] = {
                            'url': url,
                            'title': title,
                            'domain': domain,
                            'start_time': current_time,
                            'is_active': True
                        }
            
            # İlk kez URL bilgisi alınıyorsa
            elif not self.current_url and url:
                self.current_url = url
                self.current_title = title
                self.current_domain = domain
                self.current_start_time = current_time
                
                # Yeni sekmeyi aktif sekmeler sözlüğüne ekle
                if url and domain:
                    tab_key = f"{domain}:{url}"
                    self.active_tabs[tab_key] = {
                        'url': url,
                        'title': title,
                        'domain': domain,
                        'start_time': current_time,
                        'is_active': True
                    }
        else:
            # Her 60 saniyede bir çalışan tarayıcıları kontrol et
            if not hasattr(self, 'last_browser_check') or (current_time - self.last_browser_check).total_seconds() > 60:
                self._check_running_browsers()
                self.last_browser_check = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son URL aktivitesini kaydet
        if self.current_url:
            end_time = datetime.datetime.now()
            duration_seconds = int((end_time - self.current_start_time).total_seconds())
            
            if duration_seconds > 3:
                if not self.current_domain or not any(excluded.lower() in self.current_domain.lower() for excluded in EXCLUDED_WEBSITES):
                    try:
                        # Aktif pencere ID'sini al (eğer varsa)
                        window_id = None
                        if self.window_tracker:
                            window_id = self.window_tracker.get_last_window_id()
                        
                        # Veritabanına kaydet
                        browser_activity = BrowserActivity(
                            session_id=self.session_id,
                            timestamp=self.current_start_time,
                            url=self.current_url,
                            title=self.current_title,
                            domain=self.current_domain,
                            duration=duration_seconds,
                            window_id=window_id
                        )
                        self.db_session.add(browser_activity)
                        self.db_session.commit()
                        self.logger.info(f"Son aktivite kaydedildi: {self.current_domain} ({duration_seconds}s)")
                    except Exception as e:
                        self.logger.error(f"Son aktivite kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
        
        self.current_url = None
        self.current_title = None
        self.current_domain = None
        self.current_start_time = None
        self.active_tabs = {}
    
    def _get_active_browser_window(self):
        """Aktif tarayıcı penceresi bilgilerini al.
        
        Returns:
            dict: Tarayıcı bilgileri (url, title, domain) veya None.
        """
        # Pencere izleyicisinden aktif pencere bilgilerini al
        if not self.window_tracker:
            return None
        
        # Aktif pencere bilgilerini al
        window_info = None
        try:
            # Pencere izleyicisinin _get_active_window_info metodunu çağır
            window_info = self.window_tracker._get_active_window_info()
        except Exception as e:
            self.logger.error(f"Aktif pencere bilgileri alınırken hata oluştu: {e}")
            return None
        
        if not window_info:
            return None
        
        # Tarayıcı kontrolü
        app_name = window_info.get('application_name', '').lower()
        window_title = window_info.get('window_title', '')
        
        # Uygulama adı tarayıcı mı kontrol et
        is_browser = False
        for browser in self.browsers:
            if browser.lower() in app_name:
                is_browser = True
                break
        
        if not is_browser:
            # Tarayıcı başlık desenlerini kontrol et (uygulama adı tarayıcı olmasa bile)
            for pattern in self.browser_title_patterns:
                if re.search(pattern, window_title):
                    is_browser = True
                    break
        
        if not is_browser:
            return None
        
        # URL ve başlık bilgilerini ayır
        url = None
        title = window_title
        domain = None
        
        # URL desenleri için kontrol et
        for pattern in self.url_patterns:
            matches = re.search(pattern, window_title)
            if matches:
                url_part = matches.group(0)
                if not url_part.startswith(('http://', 'https://')):
                    url_part = 'https://' + url_part
                
                url = url_part
                domain = matches.group(1)
                
                # Başlığı URL'den temizle
                title = window_title.replace(matches.group(0), '').strip(' -|')
                break
        
        # Eğer URL bulunamadıysa, tarayıcı başlık desenlerini kontrol et
        if not url:
            for pattern in self.browser_title_patterns:
                matches = re.search(pattern, window_title)
                if matches:
                    title = matches.group(1).strip()
                    domain = "unknown"
                    url = "unknown"
                    break
        
        # Eğer hala URL bulunamadıysa, tarayıcı başlığından tahmin et
        if not url and ' - ' in window_title:
            parts = window_title.split(' - ')
            if len(parts) > 1 and parts[-1].lower() in [b.replace('.exe', '') for b in self.browsers]:
                title = ' - '.join(parts[:-1])
                domain = "unknown"
                url = "unknown"
        
        # Eğer hala URL bulunamadıysa, en azından tarayıcı olduğunu biliyoruz
        if not url:
            url = "unknown"
            domain = "unknown"
        
        return {
            'url': url,
            'title': title,
            'domain': domain
        }
    
    def get_active_tab_duration(self, domain, url):
        """Belirli bir sekmenin aktif olduğu toplam süreyi döndür.
        
        Args:
            domain: Alan adı.
            url: URL.
            
        Returns:
            int: Toplam süre (saniye cinsinden) veya 0.
        """
        tab_key = f"{domain}:{url}"
        if tab_key in self.active_tabs:
            tab_data = self.active_tabs[tab_key]
            if tab_data['is_active']:
                # Eğer sekme hala aktifse, şu ana kadar geçen süreyi hesapla
                current_time = datetime.datetime.now()
                return int((current_time - tab_data['start_time']).total_seconds())
        return 0 