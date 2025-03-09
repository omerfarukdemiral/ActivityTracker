"""
Cursor Aktivite Takipçisi Ana Modülü.

Bu modül, uygulamanın ana giriş noktasıdır.
"""
import os
import sys
import argparse
import logging
import platform

# İşletim sistemine göre modülleri import et
system = platform.system()
if system == 'Windows':
    from data_collection.windows_service import install_service
elif system == 'Darwin':  # MacOS
    from data_collection.macos_daemon import install_daemon
else:
    print(f"Desteklenmeyen işletim sistemi: {system}")
    sys.exit(1)

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Komut satırı argümanlarını ayrıştır.
    
    Returns:
        argparse.Namespace: Ayrıştırılan argümanlar.
    """
    parser = argparse.ArgumentParser(description='Cursor Aktivite Takipçisi')
    
    # Alt komutlar
    subparsers = parser.add_subparsers(dest='command', help='Komutlar')
    
    # Servis komutları
    service_parser = subparsers.add_parser('service', help='Servis komutları')
    service_parser.add_argument('action', choices=['install', 'start', 'stop', 'remove', 'restart'], help='Servis işlemi')
    
    # Veri işleme komutları
    process_parser = subparsers.add_parser('process', help='Veri işleme komutları')
    process_parser.add_argument('--date', help='İşlenecek tarih (YYYY-MM-DD formatında)')
    
    # İçerik yayınlama komutları
    publish_parser = subparsers.add_parser('publish', help='İçerik yayınlama komutları')
    publish_parser.add_argument('--date', help='Yayınlanacak tarih (YYYY-MM-DD formatında)')
    
    return parser.parse_args()

def main():
    """Ana fonksiyon."""
    args = parse_args()
    
    # İşletim sistemini kontrol et
    system = platform.system()
    
    if args.command == 'service':
        # Servis komutları
        if system == 'Windows':
            # Windows servis komutları
            if args.action == 'install':
                logger.info("Windows servisi yükleniyor...")
                sys.argv = [sys.argv[0], 'install']
                install_service()
            elif args.action == 'start':
                logger.info("Windows servisi başlatılıyor...")
                sys.argv = [sys.argv[0], 'start']
                install_service()
            elif args.action == 'stop':
                logger.info("Windows servisi durduruluyor...")
                sys.argv = [sys.argv[0], 'stop']
                install_service()
            elif args.action == 'remove':
                logger.info("Windows servisi kaldırılıyor...")
                sys.argv = [sys.argv[0], 'remove']
                install_service()
            elif args.action == 'restart':
                logger.info("Windows servisi yeniden başlatılıyor...")
                sys.argv = [sys.argv[0], 'restart']
                install_service()
        elif system == 'Darwin':  # MacOS
            # MacOS daemon komutları
            if args.action == 'install' or args.action == 'start':
                logger.info("MacOS daemon'u başlatılıyor...")
                sys.argv = [sys.argv[0], 'start']
                install_daemon()
            elif args.action == 'stop':
                logger.info("MacOS daemon'u durduruluyor...")
                sys.argv = [sys.argv[0], 'stop']
                install_daemon()
            elif args.action == 'restart':
                logger.info("MacOS daemon'u yeniden başlatılıyor...")
                sys.argv = [sys.argv[0], 'restart']
                install_daemon()
            elif args.action == 'remove':
                logger.info("MacOS daemon'u kaldırılıyor...")
                sys.argv = [sys.argv[0], 'stop']
                install_daemon()
                logger.info("MacOS daemon'u kaldırıldı.")
        else:
            logger.error(f"Desteklenmeyen işletim sistemi: {system}")
            sys.exit(1)
    elif args.command == 'process':
        # Veri işleme komutları
        logger.info("Veri işleme modülü henüz uygulanmadı.")
        # TODO: Veri işleme modülünü çağır
    elif args.command == 'publish':
        # İçerik yayınlama komutları
        logger.info("İçerik yayınlama modülü henüz uygulanmadı.")
        # TODO: İçerik yayınlama modülünü çağır
    else:
        logger.error("Geçersiz komut. Yardım için 'python src/main.py -h' komutunu kullanın.")
        sys.exit(1)

if __name__ == '__main__':
    main() 