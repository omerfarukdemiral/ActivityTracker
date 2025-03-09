"""
Veri toplama modülü için yapılandırma ayarları.
"""
import os
import json
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Veritabanı ayarları
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/activity_data.db")

# Veri toplama ayarları
COLLECTION_INTERVAL = int(os.getenv("COLLECTION_INTERVAL", "5"))  # Saniye cinsinden

# İzleme özellikleri
ENABLE_KEYBOARD_TRACKING = os.getenv("ENABLE_KEYBOARD_TRACKING", "true").lower() == "true"
ENABLE_MOUSE_TRACKING = os.getenv("ENABLE_MOUSE_TRACKING", "true").lower() == "true"
ENABLE_WINDOW_TRACKING = os.getenv("ENABLE_WINDOW_TRACKING", "true").lower() == "true"
ENABLE_FILE_TRACKING = os.getenv("ENABLE_FILE_TRACKING", "true").lower() == "true"
ENABLE_BROWSER_TRACKING = os.getenv("ENABLE_BROWSER_TRACKING", "true").lower() == "true"
ENABLE_GAME_TRACKING = os.getenv("ENABLE_GAME_TRACKING", "true").lower() == "true"

# Gizlilik ayarları
def parse_json_env(env_var, default=None):
    """JSON formatındaki çevre değişkenlerini ayrıştırır."""
    value = os.getenv(env_var)
    if not value:
        return default or []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        print(f"Uyarı: {env_var} JSON olarak ayrıştırılamadı. Varsayılan değer kullanılıyor.")
        return default or []

EXCLUDED_APPS = parse_json_env("EXCLUDED_APPS", [])
EXCLUDED_WEBSITES = parse_json_env("EXCLUDED_WEBSITES", [])
EXCLUDED_DIRECTORIES = parse_json_env("EXCLUDED_DIRECTORIES", [])

# Servis ayarları
SERVICE_NAME = "CursorActivityTracker"
SERVICE_DISPLAY_NAME = "Cursor Activity Tracker Service"
SERVICE_DESCRIPTION = "Kullanıcı aktivitelerini izleyen ve kaydeden servis."

# Veri yolları
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")

# Dizinlerin varlığını kontrol et ve oluştur
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True) 