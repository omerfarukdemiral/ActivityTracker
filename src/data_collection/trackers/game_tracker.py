"""
Oyun izleyicisi.

Bu modül, oyun aktivitelerini izlemek ve kaydetmek için kullanılır.
"""
import time
import logging
import datetime
import os
import psutil
import re
from .base_tracker import BaseTracker
from .window_tracker import WindowTracker
from ..config import COLLECTION_INTERVAL, ENABLE_GAME_TRACKING
from ..database import GameActivity

logger = logging.getLogger(__name__)

class GameTracker(BaseTracker):
    """Oyun aktivitelerini izleyen sınıf."""
    
    def __init__(self, session_id):
        """İzleyiciyi başlat.
        
        Args:
            session_id: Aktivite oturumu ID'si.
        """
        super().__init__(session_id)
        self.current_game = None
        self.current_platform = None
        self.current_start_time = None
        self.window_tracker = None
        
        # Bilinen oyun platformları ve klasörleri
        self.game_platforms = {
            "Steam": [
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), "Steam"),
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "Steam")
            ],
            "Epic Games": [
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), "Epic Games"),
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "Epic Games")
            ],
            "Origin": [
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), "Origin"),
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "Origin")
            ],
            "Ubisoft": [
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), "Ubisoft"),
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "Ubisoft")
            ],
            "GOG Galaxy": [
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), "GOG Galaxy"),
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "GOG Galaxy")
            ],
            "Blizzard": [
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), "Battle.net"),
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "Battle.net")
            ]
        }
        
        # Bilinen oyun işlem adları
        self.game_launchers = [
            "steam.exe",
            "epicgameslauncher.exe",
            "origin.exe",
            "upc.exe",
            "galaxyclient.exe",
            "battle.net.exe"
        ]
        
        # Bilinen oyun uzantıları
        self.game_extensions = [".exe"]
        
        # Bilinen oyun klasörleri
        self.game_folders = ["games", "steamapps", "common"]
        
        # Hariç tutulacak uygulamalar (oyun olarak algılanmaması gerekenler)
        self.excluded_apps = [
            "chrome.exe", "firefox.exe", "msedge.exe", "opera.exe", "brave.exe", "safari.exe", "iexplore.exe",
            "explorer.exe", "notepad.exe", "cmd.exe", "powershell.exe", "code.exe", "cursor.exe", "cursor",
            "ActivityTracker", "python.exe", "python", "windowsterminal.exe", "terminal"
        ]
        
        # Bilinen popüler oyunlar listesi
        self.known_games = [
            "GTA5.exe", "GTAV.exe", "Cyberpunk2077.exe", "Witcher3.exe", "Fortnite.exe", "LeagueOfLegends.exe",
            "Valorant.exe", "CSGO.exe", "CounterStrike2.exe", "Dota2.exe", "Minecraft.exe", "RocketLeague.exe",
            "Apex.exe", "ApexLegends.exe", "Overwatch.exe", "CallOfDuty.exe", "FIFA", "NBA2K", "Battlefield",
            "Rainbow6.exe", "PUBG.exe", "AmongUs.exe", "FallGuys.exe", "Roblox.exe", "WorldOfWarcraft.exe",
            "Hearthstone.exe", "Diablo", "Starcraft", "Warcraft", "HalfLife", "Portal", "Left4Dead", "TeamFortress",
            "DarkSouls", "EldenRing", "Sekiro", "Destiny", "AssassinsCreed", "FarCry", "Borderlands", "Skyrim",
            "Fallout", "ResidentEvil", "MonsterHunter", "FinalFantasy", "DevilMayCry", "MetalGear", "Halo",
            "Gears", "Forza", "GranTurismo", "NeedForSpeed", "TheLastOfUs", "GodOfWar", "Uncharted", "SpiderMan",
            "Batman", "Tomb", "Hitman", "JustCause", "MassEffect", "DragonAge", "Civilization", "AgeOfEmpires",
            "TotalWar", "StarWars", "RedDead", "Mafia", "SaintsRow", "WatchDogs", "Division", "Ghost", "Splinter",
            "Doom", "Quake", "Wolfenstein", "Prey", "Dishonored", "Bioshock", "Crysis", "FarCry", "Metro", "Stalker",
            "Witcher", "Cyberpunk", "Deus", "Thief", "Outlast", "Amnesia", "Resident", "Silent", "Dead", "Evil",
            "Dying", "Left", "Walking", "Zombie", "Survival", "Craft", "Mine", "Terraria", "Stardew", "Sims",
            "Cities", "Planet", "Zoo", "Tycoon", "Simulator", "Flight", "Truck", "Euro", "American", "Farm",
            "Racing", "Sport", "Ball", "Football", "Soccer", "Basketball", "Hockey", "Golf", "Tennis", "Wrestling",
            "Fight", "Mortal", "Street", "Tekken", "Soul", "Guilty", "BlazBlue", "King", "Super", "Smash", "Bros",
            "Mario", "Zelda", "Pokemon", "Kirby", "Metroid", "Splatoon", "Animal", "Crossing", "Fire", "Emblem",
            "Xenoblade", "Tales", "Persona", "Shin", "Megami", "Tensei", "Dragon", "Quest", "Fantasy", "Kingdom",
            "Hearts", "Nier", "Octopath", "Bravely", "Chrono", "Mana", "Saga", "Xeno", "Valkyria", "Disgaea",
            "Atelier", "Harvest", "Moon", "Story", "Seasons", "Rune", "Factory"
        ]
        
        # Çalışan oyunları kontrol et
        self._check_running_games()
    
    def _check_running_games(self):
        """Çalışan oyunları kontrol et."""
        try:
            running_games = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_name = proc.info['name'].lower()
                    proc_exe = proc.info.get('exe', '')
                    
                    # Hariç tutulan uygulamaları atla
                    if any(excluded.lower() in proc_name for excluded in self.excluded_apps):
                        continue
                    
                    # Bilinen oyun platformlarını kontrol et
                    is_game_platform = False
                    for platform, paths in self.game_platforms.items():
                        if proc_exe and any(path.lower() in proc_exe.lower() for path in paths if path):
                            is_game_platform = True
                            break
                    
                    # Bilinen oyunları kontrol et
                    is_known_game = False
                    for game in self.known_games:
                        if game.lower() in proc_name or (proc_exe and game.lower() in proc_exe.lower()):
                            is_known_game = True
                            running_games.append(proc_name)
                            break
                    
                    # Oyun klasörlerini kontrol et
                    is_in_game_folder = False
                    if proc_exe:
                        for folder in self.game_folders:
                            if folder.lower() in proc_exe.lower():
                                is_in_game_folder = True
                                running_games.append(proc_name)
                                break
                    
                    # Eğer oyun platformu değilse ve bilinen bir oyun değilse ve oyun klasöründe değilse, atla
                    if not (is_game_platform or is_known_game or is_in_game_folder):
                        continue
                    
                    # Oyun işlem adlarını atla (bunlar launcher'lar, oyunun kendisi değil)
                    if proc_name in self.game_launchers:
                        continue
                    
                    running_games.append(proc_name)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if running_games:
                self.logger.info(f"Çalışan oyunlar: {', '.join(set(running_games))}")
        except Exception as e:
            self.logger.error(f"Çalışan oyunlar kontrol edilirken hata oluştu: {e}")
    
    def _setup(self):
        """İzleyiciyi hazırla."""
        if not ENABLE_GAME_TRACKING:
            self.logger.info("Oyun izleme devre dışı bırakıldı")
            self.stop()
            return
        
        # Pencere izleyicisini oluştur (sadece referans için, başlatma)
        self.window_tracker = WindowTracker(self.session_id)
        
        # Mevcut oyun bilgilerini temizle
        self.current_game = None
        self.current_platform = None
        self.current_start_time = None
    
    def _collect_data(self):
        """Veri topla."""
        if not ENABLE_GAME_TRACKING:
            return
        
        # Aktif oyun bilgilerini al
        game_info = self._get_active_game()
        
        if game_info:
            game_name = game_info.get('game_name')
            platform = game_info.get('platform')
            
            # Oyun değiştiyse, önceki oyun için süreyi kaydet
            if self.current_game and game_name != self.current_game:
                # Önceki oyun için süreyi hesapla
                end_time = datetime.datetime.now()
                duration_seconds = int((end_time - self.current_start_time).total_seconds())
                
                # Minimum süre kontrolü (30 saniyeden fazla ise kaydet)
                if duration_seconds > 30:
                    try:
                        # Aktif pencere ID'sini al (eğer varsa)
                        window_id = None
                        if self.window_tracker:
                            window_id = self.window_tracker.get_last_window_id()
                        
                        # Veritabanına kaydet
                        game_activity = GameActivity(
                            session_id=self.session_id,
                            timestamp=self.current_start_time,
                            game_name=self.current_game,
                            platform=self.current_platform,
                            duration=duration_seconds,
                            window_id=window_id
                        )
                        self.db_session.add(game_activity)
                        self.db_session.commit()
                        self.logger.info(f"Aktivite tespit edildi: {self.current_game} ({duration_seconds}s)")
                    except Exception as e:
                        self.logger.error(f"Aktivite kaydedilirken hata oluştu: {e}")
                        self.db_session.rollback()
                
                # Yeni oyunu ayarla
                self.current_game = game_name
                self.current_platform = platform
                self.current_start_time = end_time
            
            # İlk kez oyun bilgisi alınıyorsa
            elif not self.current_game and game_name:
                self.current_game = game_name
                self.current_platform = platform
                self.current_start_time = datetime.datetime.now()
        else:
            # Her 60 saniyede bir çalışan oyunları kontrol et
            current_time = datetime.datetime.now()
            if not hasattr(self, 'last_game_check') or (current_time - self.last_game_check).total_seconds() > 60:
                self._check_running_games()
                self.last_game_check = current_time
        
        # Veri toplama aralığı kadar bekle
        time.sleep(COLLECTION_INTERVAL)
    
    def _cleanup(self):
        """Kaynakları temizle."""
        # Son oyun aktivitesini kaydet
        if self.current_game:
            end_time = datetime.datetime.now()
            duration_seconds = int((end_time - self.current_start_time).total_seconds())
            
            if duration_seconds > 30:
                try:
                    # Aktif pencere ID'sini al (eğer varsa)
                    window_id = None
                    if self.window_tracker:
                        window_id = self.window_tracker.get_last_window_id()
                    
                    # Veritabanına kaydet
                    game_activity = GameActivity(
                        session_id=self.session_id,
                        timestamp=self.current_start_time,
                        game_name=self.current_game,
                        platform=self.current_platform,
                        duration=duration_seconds,
                        window_id=window_id
                    )
                    self.db_session.add(game_activity)
                    self.db_session.commit()
                    self.logger.info(f"Son aktivite kaydedildi: {self.current_game} ({duration_seconds}s)")
                except Exception as e:
                    self.logger.error(f"Son aktivite kaydedilirken hata oluştu: {e}")
                    self.db_session.rollback()
        
        self.current_game = None
        self.current_platform = None
        self.current_start_time = None
    
    def _get_active_game(self):
        """Aktif oyun bilgilerini al.
        
        Returns:
            dict: Oyun bilgileri (game_name, platform) veya None.
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
        
        # İşlem bilgilerini al
        process_id = window_info.get('process_id')
        app_name = window_info.get('application_name', '').lower()
        window_title = window_info.get('window_title', '')
        
        # Hariç tutulan uygulamaları kontrol et
        if any(excluded.lower() in app_name for excluded in self.excluded_apps):
            return None
        
        # Tarayıcı ve Cursor gibi uygulamaları kontrol et ve hariç tut
        if "chrome" in app_name or "firefox" in app_name or "edge" in app_name or "opera" in app_name or "brave" in app_name or "safari" in app_name or "cursor" in app_name:
            return None
        
        if not process_id:
            return None
        
        try:
            process = psutil.Process(process_id)
            exe_path = process.exe()
            
            # Oyun platformunu belirle
            platform = self._detect_game_platform(exe_path)
            
            # Oyun adını belirle
            game_name = self._get_game_name(process, exe_path, window_title)
            
            # Eğer oyun adı bulunamadıysa veya hariç tutulan bir uygulama ise, None döndür
            if not game_name or any(excluded.lower() in game_name.lower() for excluded in self.excluded_apps):
                return None
            
            # Bilinen oyunları kontrol et
            is_known_game = False
            for game in self.known_games:
                if game.lower() in game_name.lower() or game.lower() in exe_path.lower():
                    is_known_game = True
                    break
            
            # Oyun klasörlerini kontrol et
            is_in_game_folder = False
            for folder in self.game_folders:
                if folder.lower() in exe_path.lower():
                    is_in_game_folder = True
                    break
            
            # Eğer bilinen bir oyun değilse ve oyun klasöründe değilse, None döndür
            if not (is_known_game or is_in_game_folder):
                return None
            
            return {
                'game_name': game_name,
                'platform': platform
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            self.logger.error(f"İşlem bilgileri alınırken hata oluştu: {e}")
        
        return None
    
    def _detect_game_platform(self, exe_path):
        """Oyun platformunu belirle.
        
        Args:
            exe_path: Yürütülebilir dosya yolu.
        
        Returns:
            str: Platform adı veya "Unknown".
        """
        if not exe_path:
            return "Unknown"
        
        # Platform klasörlerini kontrol et
        for platform, paths in self.game_platforms.items():
            for path in paths:
                if path and exe_path.lower().startswith(path.lower()):
                    return platform
        
        # Bilinen oyun işlem adlarını kontrol et
        exe_name = os.path.basename(exe_path).lower()
        if exe_name in self.game_launchers:
            for platform, process in [
                ("Steam", "steam.exe"),
                ("Epic Games", "epicgameslauncher.exe"),
                ("Origin", "origin.exe"),
                ("Ubisoft", "upc.exe"),
                ("GOG Galaxy", "galaxyclient.exe"),
                ("Blizzard", "battle.net.exe")
            ]:
                if exe_name == process:
                    return platform
        
        return "Unknown"
    
    def _get_game_name(self, process, exe_path, window_title):
        """Oyun adını belirle.
        
        Args:
            process: psutil.Process nesnesi.
            exe_path: Yürütülebilir dosya yolu.
            window_title: Pencere başlığı.
        
        Returns:
            str: Oyun adı veya None.
        """
        if not exe_path:
            return None
        
        # Exe adını al
        exe_name = os.path.basename(exe_path)
        name, ext = os.path.splitext(exe_name)
        
        # Oyun uzantısı kontrolü
        if ext.lower() not in self.game_extensions:
            return None
        
        # Bilinen oyun işlem adlarını kontrol et
        if exe_name.lower() in self.game_launchers:
            # Bu bir oyun platformu, oyun değil
            return None
        
        # Oyun klasörlerini kontrol et
        for folder in self.game_folders:
            if folder.lower() in exe_path.lower():
                # Muhtemelen bir oyun
                break
        else:
            # Oyun klasörü bulunamadı, ancak yine de oyun olabilir
            # Pencere başlığını kontrol et
            if window_title and len(window_title) > 0:
                # Pencere başlığını kullan
                return window_title
            
            # Exe adını kullan
            return name
        
        # Exe adını kullan
        return name 