import os
from dotenv import load_dotenv

# Загружаем .env
if os.path.exists('.env'):
    load_dotenv()

class Config:
    # База данных Supabase
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
    
    # Email (mail.ru)
    MAIL_SERVER = os.environ.get('EMAIL_HOST', 'smtp.mail.ru')
    MAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get('EMAIL_USER')
    MAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('EMAIL_FROM', 'verification@skytrack.c6t.ru')
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-me')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Google Maps
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    
    # Настройки обновления
    FLIGHT_UPDATE_INTERVAL = 5
    
    @classmethod
    def validate_config(cls):
        """Проверка переменных окружения"""
        required = ['DATABASE_URL', 'OPENSKY_CLIENT_ID', 'OPENSKY_CLIENT_SECRET', 
                   'MAIL_USERNAME', 'MAIL_PASSWORD', 'SECRET_KEY']
        
        missing = [v for v in required if not os.environ.get(v)]
        
        if missing:
            print(f"⚠️ Отсутствуют: {', '.join(missing)}")
            return False
        return True
