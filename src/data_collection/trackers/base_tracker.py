"""
Temel izleyici sınıfı.

Bu modül, tüm izleyicilerin temel aldığı soyut sınıfı içerir.
"""
import abc
import threading
import logging
import time
from ..database import get_session

logger = logging.getLogger(__name__)

class BaseTracker(abc.ABC):
    """Tüm izleyiciler için temel sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        self.session_id = session_id
        self.is_running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.db_session = None
        self.logger = logging.getLogger(f'data_collection.trackers.{self.__class__.__name__.lower()}')
    
    def start(self):
        """İzleyiciyi başlat."""
        if self.is_running:
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"{self.__class__.__name__} başlatıldı")
    
    def stop(self):
        """İzleyiciyi durdur."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5.0)
        
        if self.db_session:
            self.db_session.close()
            self.db_session = None
        
        self.logger.info(f"{self.__class__.__name__} durduruldu")
    
    def _run(self):
        """İzleyici ana döngüsü."""
        try:
            self.db_session = get_session()
            self._setup()
            
            while self.is_running and not self.stop_event.is_set():
                try:
                    self._collect_data()
                except Exception as e:
                    self.logger.error(f"Veri toplarken hata oluştu: {e}")
                
                # Durdurma sinyalini kontrol et
                if self.stop_event.wait(timeout=1.0):
                    break
            
            self._cleanup()
        except Exception as e:
            self.logger.error(f"Çalışırken hata oluştu: {e}")
            self.is_running = False
        finally:
            if self.db_session:
                self.db_session.close()
                self.db_session = None
    
    @abc.abstractmethod
    def _setup(self):
        """İzleyiciyi hazırla."""
        pass
    
    @abc.abstractmethod
    def _collect_data(self):
        """Veri topla."""
        pass
    
    @abc.abstractmethod
    def _cleanup(self):
        """Kaynakları temizle."""
        pass 