"""
Veritabanı modeli ve bağlantı işlevleri.
"""
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from .config import DATABASE_PATH

# Veritabanı dizininin varlığını kontrol et
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# SQLAlchemy engine ve session oluştur
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
Session = sessionmaker(bind=engine)
Base = declarative_base()

class ActivitySession(Base):
    """Kullanıcı aktivite oturumu."""
    __tablename__ = 'activity_sessions'
    
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, default=datetime.datetime.now)
    end_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # İlişkiler
    window_activities = relationship("WindowActivity", back_populates="session")
    keyboard_activities = relationship("KeyboardActivity", back_populates="session")
    mouse_activities = relationship("MouseActivity", back_populates="session")
    file_activities = relationship("FileActivity", back_populates="session")
    browser_activities = relationship("BrowserActivity", back_populates="session")
    game_activities = relationship("GameActivity", back_populates="session")

class WindowActivity(Base):
    """Aktif pencere aktivitesi."""
    __tablename__ = 'window_activities'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('activity_sessions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.now)
    window_title = Column(String(255))
    application_name = Column(String(100))
    process_id = Column(Integer)
    duration = Column(Integer, default=0)  # Saniye cinsinden
    
    # İlişkiler
    session = relationship("ActivitySession", back_populates="window_activities")

class KeyboardActivity(Base):
    """Klavye aktivitesi (tuş vuruşları sayısı, vb.)."""
    __tablename__ = 'keyboard_activities'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('activity_sessions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.now)
    key_count = Column(Integer, default=0)
    window_id = Column(Integer, ForeignKey('window_activities.id'), nullable=True)
    
    # İlişkiler
    session = relationship("ActivitySession", back_populates="keyboard_activities")
    window = relationship("WindowActivity")

class MouseActivity(Base):
    """Fare aktivitesi (tıklama sayısı, hareket, vb.)."""
    __tablename__ = 'mouse_activities'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('activity_sessions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.now)
    click_count = Column(Integer, default=0)
    movement_pixels = Column(Integer, default=0)
    window_id = Column(Integer, ForeignKey('window_activities.id'), nullable=True)
    
    # İlişkiler
    session = relationship("ActivitySession", back_populates="mouse_activities")
    window = relationship("WindowActivity")

class FileActivity(Base):
    """Dosya sistemi aktivitesi."""
    __tablename__ = 'file_activities'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('activity_sessions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.now)
    file_path = Column(String(512))
    action = Column(String(50))  # created, modified, deleted, etc.
    file_type = Column(String(50))  # extension or mime type
    window_id = Column(Integer, ForeignKey('window_activities.id'), nullable=True)
    
    # İlişkiler
    session = relationship("ActivitySession", back_populates="file_activities")
    window = relationship("WindowActivity")

class BrowserActivity(Base):
    """Web tarayıcı aktivitesi."""
    __tablename__ = 'browser_activities'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('activity_sessions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.now)
    url = Column(String(1024))
    title = Column(String(255))
    domain = Column(String(255))
    duration = Column(Integer, default=0)  # Saniye cinsinden
    window_id = Column(Integer, ForeignKey('window_activities.id'), nullable=True)
    
    # İlişkiler
    session = relationship("ActivitySession", back_populates="browser_activities")
    window = relationship("WindowActivity")

class GameActivity(Base):
    """Oyun aktivitesi."""
    __tablename__ = 'game_activities'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('activity_sessions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.now)
    game_name = Column(String(255))
    platform = Column(String(100))  # Steam, Epic, etc.
    duration = Column(Integer, default=0)  # Saniye cinsinden
    window_id = Column(Integer, ForeignKey('window_activities.id'), nullable=True)
    
    # İlişkiler
    session = relationship("ActivitySession", back_populates="game_activities")
    window = relationship("WindowActivity")

class DailySummary(Base):
    """Günlük aktivite özeti."""
    __tablename__ = 'daily_summaries'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.datetime.now)
    total_active_time = Column(Integer, default=0)  # Saniye cinsinden
    productivity_score = Column(Float, default=0.0)  # 0-100 arası
    summary_text = Column(Text)
    categories = Column(String(512))  # JSON formatında kategori listesi
    
    def __repr__(self):
        return f"<DailySummary(date='{self.date}', productivity_score={self.productivity_score})>"

def init_db():
    """Veritabanını başlat ve tabloları oluştur."""
    Base.metadata.create_all(engine)
    
def get_session():
    """Yeni bir veritabanı oturumu döndür."""
    return Session()

# Veritabanını başlat
init_db() 