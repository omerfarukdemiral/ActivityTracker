"""
MacOS daemon uygulaması.

Bu modül, MacOS'ta arka planda çalışan ve kullanıcı aktivitelerini izleyen bir daemon oluşturur.
"""
import os
import sys
import time
import logging
import datetime
import signal
import atexit
from pathlib import Path

from .config import SERVICE_NAME, LOG_DIR, COLLECTION_INTERVAL
from .trackers.window_tracker_macos import WindowTrackerMacOS
from .trackers.file_tracker_macos import FileTrackerMacOS
from .trackers.browser_tracker_macos import BrowserTrackerMacOS
from .trackers.game_tracker_macos import GameTrackerMacOS
from .database import get_session, ActivitySession

# Logging yapılandırması
log_file = os.path.join(LOG_DIR, 'macos_daemon.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ActivityTrackerDaemon:
    """MacOS daemon sınıfı."""
    
    def __init__(self):
        """Daemon'u başlat."""
        self.pidfile = f"/tmp/{SERVICE_NAME}.pid"
        self.is_running = False
        self.trackers = []
        self.session = None
    
    def daemonize(self):
        """Daemon'u arka plana al."""
        try:
            # İlk fork
            pid = os.fork()
            if pid > 0:
                # Ana süreç çıkış yapıyor
                sys.exit(0)
        except OSError as e:
            logger.error(f"İlk fork başarısız: {e}")
            sys.exit(1)
        
        # Ana süreçten bağımsızlaş
        os.chdir('/')
        os.setsid()
        os.umask(0)
        
        try:
            # İkinci fork
            pid = os.fork()
            if pid > 0:
                # İkinci ana süreç çıkış yapıyor
                sys.exit(0)
        except OSError as e:
            logger.error(f"İkinci fork başarısız: {e}")
            sys.exit(1)
        
        # Standart dosya tanımlayıcılarını yeniden yönlendir
        sys.stdout.flush()
        sys.stderr.flush()
        
        si = open(os.devnull, 'r')
        so = open(os.devnull, 'a+')
        se = open(os.devnull, 'a+')
        
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        
        # PID dosyasını oluştur
        atexit.register(self.delete_pidfile)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+') as f:
            f.write(pid + '\n')
    
    def delete_pidfile(self):
        """PID dosyasını sil."""
        os.remove(self.pidfile)
    
    def start(self):
        """Daemon'u başlat."""
        # PID dosyasını kontrol et
        try:
            with open(self.pidfile, 'r') as pf:
                pid = int(pf.read().strip())
        except IOError:
            pid = None
        
        if pid:
            # Daemon zaten çalışıyor mu kontrol et
            try:
                os.kill(pid, 0)
                logger.error(f"Daemon zaten çalışıyor (PID: {pid})")
                sys.exit(1)
            except OSError:
                # Daemon çalışmıyor, PID dosyasını sil
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
        
        # Daemon'u başlat
        self.daemonize()
        self.run()
    
    def stop(self):
        """Daemon'u durdur."""
        # PID dosyasını kontrol et
        try:
            with open(self.pidfile, 'r') as pf:
                pid = int(pf.read().strip())
        except IOError:
            pid = None
        
        if not pid:
            logger.error("Daemon çalışmıyor")
            return
        
        # Daemon'u durdur
        try:
            while True:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except OSError as e:
            if 'No such process' in str(e):
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                logger.error(f"Daemon durdurulurken hata oluştu: {e}")
                sys.exit(1)
    
    def restart(self):
        """Daemon'u yeniden başlat."""
        self.stop()
        self.start()
    
    def run(self):
        """Ana daemon döngüsü."""
        logger.info("Daemon başlatıldı")
        self.is_running = True
        
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
            logger.error("Oturum oluşturulamadığı için daemon durduruluyor")
            self.is_running = False
            return
        
        # İzleyicileri başlat
        try:
            self.trackers = [
                WindowTrackerMacOS(self.session.id),
                FileTrackerMacOS(self.session.id),
                BrowserTrackerMacOS(self.session.id),
                GameTrackerMacOS(self.session.id)
            ]
            
            for tracker in self.trackers:
                tracker.start()
                logger.info(f"{tracker.__class__.__name__} başlatıldı")
        except Exception as e:
            logger.error(f"İzleyiciler başlatılırken hata oluştu: {e}")
            self.is_running = False
            return
        
        # Sinyal işleyicilerini ayarla
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Ana döngü
        while self.is_running:
            # İzleyicilerin durumunu kontrol et
            for tracker in self.trackers:
                if not tracker.is_running:
                    try:
                        tracker.start()
                        logger.info(f"{tracker.__class__.__name__} yeniden başlatıldı")
                    except Exception as e:
                        logger.error(f"{tracker.__class__.__name__} yeniden başlatılırken hata oluştu: {e}")
            
            time.sleep(COLLECTION_INTERVAL)
    
    def signal_handler(self, signum, frame):
        """Sinyal işleyicisi."""
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
        
        logger.info("Daemon durduruldu")
        sys.exit(0)

def install_daemon():
    """Daemon'u yükle."""
    daemon = ActivityTrackerDaemon()
    
    if len(sys.argv) == 2:
        if sys.argv[1] == 'start':
            daemon.start()
        elif sys.argv[1] == 'stop':
            daemon.stop()
        elif sys.argv[1] == 'restart':
            daemon.restart()
        else:
            print(f"Bilinmeyen komut: {sys.argv[1]}")
            print("Kullanım: {0} start|stop|restart".format(sys.argv[0]))
            sys.exit(2)
    else:
        print("Kullanım: {0} start|stop|restart".format(sys.argv[0]))
        sys.exit(2)

if __name__ == '__main__':
    install_daemon() 