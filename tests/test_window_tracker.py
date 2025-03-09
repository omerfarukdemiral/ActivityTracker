"""
Pencere izleyicisi için test modülü.
"""
import unittest
import os
import sys
import time
import datetime
from unittest.mock import patch, MagicMock

# Modül yolunu ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_collection.trackers.window_tracker import WindowTracker
from src.data_collection.database import ActivitySession, WindowActivity

class TestWindowTracker(unittest.TestCase):
    """Pencere izleyicisi için test sınıfı."""
    
    @patch('src.data_collection.trackers.window_tracker.win32gui')
    @patch('src.data_collection.trackers.window_tracker.win32process')
    @patch('src.data_collection.trackers.window_tracker.psutil')
    def test_get_active_window_info(self, mock_psutil, mock_win32process, mock_win32gui):
        """_get_active_window_info metodunu test et."""
        # Mock nesnelerini yapılandır
        mock_win32gui.GetForegroundWindow.return_value = 12345
        mock_win32gui.GetWindowText.return_value = "Test Window - Notepad"
        mock_win32process.GetWindowThreadProcessId.return_value = (1, 67890)
        
        mock_process = MagicMock()
        mock_process.name.return_value = "notepad.exe"
        mock_psutil.Process.return_value = mock_process
        
        # Test için oturum oluştur
        session_id = 1
        
        # WindowTracker örneği oluştur
        tracker = WindowTracker(session_id)
        
        # _get_active_window_info metodunu çağır
        result = tracker._get_active_window_info()
        
        # Sonuçları doğrula
        self.assertIsNotNone(result)
        self.assertEqual(result['window_title'], "Test Window - Notepad")
        self.assertEqual(result['application_name'], "notepad.exe")
        self.assertEqual(result['process_id'], 67890)
        
        # Mock çağrılarını doğrula
        mock_win32gui.GetForegroundWindow.assert_called_once()
        mock_win32gui.GetWindowText.assert_called_once_with(12345)
        mock_win32process.GetWindowThreadProcessId.assert_called_once_with(12345)
        mock_psutil.Process.assert_called_once_with(67890)
    
    @patch('src.data_collection.trackers.window_tracker.get_session')
    @patch('src.data_collection.trackers.window_tracker.WindowTracker._get_active_window_info')
    def test_collect_data(self, mock_get_active_window_info, mock_get_session):
        """_collect_data metodunu test et."""
        # Mock nesnelerini yapılandır
        mock_db_session = MagicMock()
        mock_get_session.return_value = mock_db_session
        
        # İlk pencere bilgisi
        mock_get_active_window_info.side_effect = [
            {
                'window_title': "Test Window 1 - Notepad",
                'application_name': "notepad.exe",
                'process_id': 67890
            },
            {
                'window_title': "Test Window 2 - Chrome",
                'application_name': "chrome.exe",
                'process_id': 12345
            },
            None  # Üçüncü çağrı için None döndür
        ]
        
        # Test için oturum oluştur
        session_id = 1
        
        # WindowTracker örneği oluştur
        tracker = WindowTracker(session_id)
        tracker.db_session = mock_db_session
        
        # Başlangıç zamanını ayarla
        tracker.current_window = {
            'window_title': "Test Window 1 - Notepad",
            'application_name': "notepad.exe",
            'process_id': 67890
        }
        tracker.current_window_start_time = datetime.datetime.now() - datetime.timedelta(seconds=10)
        
        # _collect_data metodunu çağır
        with patch('src.data_collection.trackers.window_tracker.time.sleep') as mock_sleep:
            tracker._collect_data()
        
        # Veritabanı işlemlerini doğrula
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # İkinci çağrı için yeni pencere bilgisini doğrula
        self.assertEqual(tracker.current_window['window_title'], "Test Window 2 - Chrome")
        self.assertEqual(tracker.current_window['application_name'], "chrome.exe")
        
        # Üçüncü çağrı için _collect_data metodunu çağır
        mock_db_session.reset_mock()
        with patch('src.data_collection.trackers.window_tracker.time.sleep') as mock_sleep:
            tracker._collect_data()
        
        # Pencere değiştiği için veritabanı işlemlerini doğrula
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Pencere bilgisinin None olduğunu doğrula
        self.assertIsNone(tracker.current_window)

if __name__ == '__main__':
    unittest.main() 