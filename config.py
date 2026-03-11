import os
from dotenv import load_dotenv

# Загружаем .env
if os.path.exists('.env'):
    load_dotenv()

class Config:
    # База данных (ваша новая на Render)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # OpenSky API
    OPENSKY_CLIENT_ID = os.environ.get('OPENSKY_CLIENT_ID')
    OPENSKY_CLIENT_SECRET = os.environ.get('OPENSKY_CLIENT_SECRET')
    
    # Email settings - с правильными значениями по умолчанию
    MAIL_SERVER = os.environ.get('EMAIL_HOST', 'smtp.mail.ru')
    MAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get('EMAIL_USER')
    MAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('EMAIL_FROM', 'verification@skytrack.c6t.ru')
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-me')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Настройки обновления
    FLIGHT_UPDATE_INTERVAL = 5
    
    @classmethod
    def validate_config(cls):
        """Проверка переменных окружения"""
        required = ['DATABASE_URL', 'OPENSKY_CLIENT_ID', 'OPENSKY_CLIENT_SECRET', 'SECRET_KEY']
        
        missing = [v for v in required if not os.environ.get(v)]
        
        if missing:
            print(f"⚠️ Отсутствуют важные переменные: {', '.join(missing)}")
            return False
            
        if not cls.MAIL_USERNAME or not cls.MAIL_PASSWORD:
            print("⚠️ Почта не настроена - верификация по email работать не будет")
            
        return True
