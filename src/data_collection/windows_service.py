"""
Windows servis uygulaması.

Bu modül, Windows'ta arka planda çalışan ve kullanıcı aktivitelerini izleyen bir servis oluşturur.
"""
import os
import sys
import time
import logging
import datetime
import win32serviceutil
import win32service
import win32event
import servicemanager

from .config import SERVICE_NAME, SERVICE_DISPLAY_NAME, SERVICE_DESCRIPTION, LOG_DIR, COLLECTION_INTERVAL
from .trackers.window_tracker import WindowTracker
from .trackers.keyboard_tracker import KeyboardTracker
from .trackers.mouse_tracker import MouseTracker
from .trackers.file_tracker import FileTracker
from .trackers.browser_tracker import BrowserTracker
from .trackers.game_tracker import GameTracker
from .database import get_session, ActivitySession

# Logging yapılandırması
log_file = os.path.join(LOG_DIR, 'windows_service.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ActivityTrackerService(win32serviceutil.ServiceFramework):
    """Windows servis sınıfı."""
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    
    def __init__(self, args):
        """Servisi başlat."""
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = False
        
        # İzleyicileri başlat
        self.trackers = []
        self.session = None
        
    def SvcStop(self):
        """Servisi durdur."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.is_running = False
        
        # Aktif oturumu kapat
        if self.session:
            db_session = get_session()
            try:
                activity_session = db_session.query(ActivitySession).filter_by(id=self.session.id).first()
                if activity_session:
                    activity_session.end_time = datetime.datetime.now()
                    activity_session.is_active = False
                    db_session.commit()
                    logger.info(f"Aktivite oturumu kapatıldı: {activity_session.id}")
            except Exception as e:
                logger.error(f"Oturum kapatılırken hata oluştu: {e}")
                db_session.rollback()
            finally:
                db_session.close()
        
        # İzleyicileri durdur
        for tracker in self.trackers:
            try:
                tracker.stop()
                logger.info(f"{tracker.__class__.__name__} durduruldu")
            except Exception as e:
                logger.error(f"{tracker.__class__.__name__} durdurulurken hata oluştu: {e}")
        
        logger.info("Servis durduruldu")
    
    def SvcDoRun(self):
        """Servisi çalıştır."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.is_running = True
        self.main()
    
    def main(self):
        """Ana servis döngüsü."""
        logger.info("Servis başlatıldı")
        
        # Yeni bir aktivite oturumu oluştur
        db_session = get_session()
        try:
            self.session = ActivitySession()
            db_session.add(self.session)
            db_session.commit()
            logger.info(f"Yeni aktivite oturumu oluşturuldu: {self.session.id}")
        except Exception as e:
            logger.error(f"Oturum oluşturulurken hata oluştu: {e}")
            db_session.rollback()
            self.session = None
        finally:
            db_session.close()
        
        if not self.session:
            logger.error("Oturum oluşturulamadığı için servis durduruluyor")
            self.SvcStop()
            return
        
        # İzleyicileri başlat
        try:
            self.trackers = [
                WindowTracker(self.session.id),
                KeyboardTracker(self.session.id),
                MouseTracker(self.session.id),
                FileTracker(self.session.id),
                BrowserTracker(self.session.id),
                GameTracker(self.session.id)
            ]
            
            for tracker in self.trackers:
                tracker.start()
                logger.info(f"{tracker.__class__.__name__} başlatıldı")
        except Exception as e:
            logger.error(f"İzleyiciler başlatılırken hata oluştu: {e}")
            self.SvcStop()
            return
        
        # Ana döngü
        while self.is_running:
            # Servis durdurma sinyalini kontrol et
            if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                break
            
            # İzleyicilerin durumunu kontrol et
            for tracker in self.trackers:
                if not tracker.is_running:
                    try:
                        tracker.start()
                        logger.info(f"{tracker.__class__.__name__} yeniden başlatıldı")
                    except Exception as e:
                        logger.error(f"{tracker.__class__.__name__} yeniden başlatılırken hata oluştu: {e}")
            
            time.sleep(COLLECTION_INTERVAL)

def install_service():
    """Servisi yükle."""
    try:
        if len(sys.argv) == 1:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(ActivityTrackerService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(ActivityTrackerService)
    except Exception as e:
        logger.error(f"Servis yüklenirken hata oluştu: {e}")
        print(f"Hata: {e}")

if __name__ == '__main__':
    install_service() 