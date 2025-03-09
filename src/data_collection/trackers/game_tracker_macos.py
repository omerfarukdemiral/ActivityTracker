"""
MacOS oyun izleyicisi.

Bu modül, MacOS'ta oyun aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import os
import time
import logging
import datetime
import threading
import psutil
import Quartz
import AppKit
from pathlib import Path
from .base_tracker import BaseTracker
from ..config import ENABLE_GAME_TRACKING, EXCLUDED_APPS, COLLECTION_INTERVAL, GAME_PROCESSES
from ..database import GameActivity

logger = logging.getLogger(__name__)

# MacOS'ta popüler oyun uygulamaları
MACOS_GAME_APPS = [
    'Steam', 'Battle.net', 'Epic Games Launcher', 'Origin', 'GOG Galaxy',
    'Minecraft', 'League of Legends', 'Dota 2', 'Counter-Strike', 'Fortnite',
    'Overwatch', 'World of Warcraft', 'Hearthstone', 'Starcraft', 'Diablo',
    'Civilization', 'The Sims', 'GTA', 'Grand Theft Auto', 'Call of Duty',
    'Valorant', 'Apex Legends', 'Rocket League', 'Among Us', 'Fall Guys',
    'Roblox', 'Unity', 'Unreal', 'Godot', 'GameMaker'
]

class GameTrackerMacOS(BaseTracker):
    """MacOS'ta oyun aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.active_games = {}
        self.lock = threading.Lock()
        self.last_activity_time = None
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_GAME_TRACKING:
            self.logger.info("Oyun izleme devre dışı bırakıldı")
            self.stop()
            return
        
        self.last_activity_time = datetime.datetime.now()
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_GAME_TRACKING:
            return
        
        current_time = datetime.datetime.now()
        
        # Çalışan oyunları kontrol et
        running_games = self._get_running_games()
        
        # Yeni başlayan oyunları tespit et
        for game_name, game_info in running_games.items():
            if game_name not in self.active_games:
                # Yeni oyun başladı
                self.active_games[game_name] = {
                    'start_time': current_time,
                    'process_id': game_info['process_id'],
                    'window_title': game_info['window_title']
                }
                self.logger.info(f"Oyun başladı: {game_name}")
        
        # Kapanan oyunları tespit et
        closed_games = []
        for game_name, game_info in self.active_games.items():
            if game_name not in running_games:
                # Oyun kapandı
                closed_games.append(game_name)
                
                # Oyun süresini hesapla
                start_time = game_info['start_time']
                duration_seconds = int((current_time - start_time).total_seconds())
                
                # Minimum süre kontrolü (1 dakikadan fazla ise kaydet)
                if duration_seconds > 60:
                    try:
                        # Veritabanına kaydet
                        game_activity = GameActivity(
                            session_id=self.session_id,
                            timestamp=start_time,
                            game_name=game_name,
                            window_title=game_info['window_title'],
                            process_id=game_info['process_id'],
                            duration=duration_seconds
                        )
                        self.db_session.add(game_activity)
                        self.db_session.commit()
                        self.logger.info(f"Oyun aktivitesi kaydedildi: {game_name} ({duration_seconds}s)")
                    except Exception as e:
                        self.logger.error(f"Oyun aktivitesi kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
        
        # Kapanan oyunları listeden çıkar
        for game_name in closed_games:
            del self.active_games[game_name]
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Aktif oyunları kaydet
        current_time = datetime.datetime.now()
        
        for game_name, game_info in self.active_games.items():
            # Oyun süresini hesapla
            start_time = game_info['start_time']
            duration_seconds = int((current_time - start_time).total_seconds())
            
            # Minimum süre kontrolü (1 dakikadan fazla ise kaydet)
            if duration_seconds > 60:
                try:
                    # Veritabanına kaydet
                    game_activity = GameActivity(
                        session_id=self.session_id,
                        timestamp=start_time,
                        game_name=game_name,
                        window_title=game_info['window_title'],
                        process_id=game_info['process_id'],
                        duration=duration_seconds
                    )
                    self.db_session.add(game_activity)
                    self.db_session.commit()
                    self.logger.info(f"Son oyun aktivitesi kaydedildi: {game_name} ({duration_seconds}s)")
                except Exception as e:
                    self.logger.error(f"Son oyun aktivitesi kaydedilirken hata oluştu: {e}")
                    self.db_session.rollback()
        
        self.active_games = {}
        self.last_activity_time = None
    
    def _get_running_games(self):
        """Çalışan oyunları tespit et.
        
        Returns:
            dict: Çalışan oyunlar.
        """
        running_games = {}
        
        try:
            # Çalışan uygulamaları al
            running_apps = AppKit.NSWorkspace.sharedWorkspace().runningApplications()
            
            for app in running_apps:
                try:
                    # Uygulama adını al
                    app_name = app.localizedName()
                    if not app_name:
                        continue
                    
                    # İşlem ID'sini al
                    process_id = app.processIdentifier()
                    
                    # Oyun olup olmadığını kontrol et
                    is_game = False
                    
                    # Uygulama adına göre kontrol et
                    for game_name in MACOS_GAME_APPS:
                        if game_name.lower() in app_name.lower():
                            is_game = True
                            break
                    
                    # İşlem adına göre kontrol et
                    if not is_game:
                        try:
                            process = psutil.Process(process_id)
                            process_name = process.name().lower()
                            
                            for game_process in GAME_PROCESSES:
                                if game_process.lower() in process_name:
                                    is_game = True
                                    break
                        except:
                            pass
                    
                    # Oyun ise, pencere başlığını al
                    if is_game:
                        window_title = "Unknown"
                        
                        # Quartz ile tüm pencereleri al
                        window_list = Quartz.CGWindowListCopyWindowInfo(
                            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                            Quartz.kCGNullWindowID
                        )
                        
                        # Uygulamanın pencerelerini bul
                        for window in window_list:
                            if window.get('kCGWindowOwnerPID', 0) == process_id:
                                # Pencere başlığını al
                                title = window.get('kCGWindowName', '')
                                if title:
                                    window_title = title
                                    break
                        
                        # Oyunu listeye ekle
                        running_games[app_name] = {
                            'process_id': process_id,
                            'window_title': window_title
                        }
                except:
                    continue
        except Exception as e:
            self.logger.error(f"Çalışan oyunlar tespit edilirken hata oluştu: {e}")
        
        return running_games
    
    def get_active_games(self):
        """Aktif oyunları döndür.
        
        Returns:
            dict: Aktif oyunlar.
        """
        return self.active_games.copy() 