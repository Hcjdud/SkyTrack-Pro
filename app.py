#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyTrack Pro - Главный файл приложения
Профессиональный трекер самолётов с Google Maps
"""

import os
import sys
from datetime import datetime, timedelta

# Импорты Flask и расширений
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (только для локальной разработки)
if os.path.exists('.env'):
    load_dotenv()
    print("✅ Загружен .env файл")
else:
    print("ℹ️ .env файл не найден, используем переменные окружения системы")

# Импорт конфигурации
from config import Config

# Проверка версий критических пакетов
import werkzeug
import flask_login
print(f"✅ Werkzeug версия: {werkzeug.__version__}")
print(f"✅ Flask-Login версия: {flask_login.__version__}")

# Импорт моделей и модулей приложения
from models import db, User
from auth import auth_bp
from email_service import mail
from opensky_client import OpenSkyClient

# Создание экземпляра приложения Flask
app = Flask(__name__)
app.config.from_object(Config)

# Проверка конфигурации
if not Config.validate_config():
    print("⚠️  Внимание: Не все переменные окружения установлены!")
    print("⚠️  Приложение может работать некорректно")

# Инициализация расширений
CORS(app, supports_credentials=True)  # Включаем CORS для всех маршрутов
db.init_app(app)  # Инициализация SQLAlchemy
mail.init_app(app)  # Инициализация Flask-Mail

# Инициализация Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # Перенаправление на страницу входа
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
login_manager.login_message_category = 'info'

# Инициализация клиента OpenSky
opensky = OpenSkyClient(
    Config.OPENSKY_CLIENT_ID,
    Config.OPENSKY_CLIENT_SECRET
)

@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID для Flask-Login"""
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        print(f"❌ Ошибка загрузки пользователя: {e}")
        return None

# Регистрация blueprint для аутентификации
app.register_blueprint(auth_bp, url_prefix='/auth')

# Создание таблиц в базе данных
with app.app_context():
    try:
        db.create_all()
        print("✅ Таблицы в базе данных созданы/проверены")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        print("⚠️ Проверьте подключение к базе данных")

@app.route('/')
@login_required
def index():
    """Главная страница с Google Maps (только для авторизованных)"""
    try:
        return render_template('index.html', 
                             username=current_user.username,
                             google_maps_api_key=Config.GOOGLE_MAPS_API_KEY,
                             update_interval=Config.FLIGHT_UPDATE_INTERVAL)
    except Exception as e:
        print(f"❌ Ошибка загрузки главной страницы: {e}")
        return "Ошибка загрузки страницы", 500

@app.route('/api/flights')
@login_required
def get_flights():
    """API endpoint для получения всех рейсов в реальном времени"""
    try:
        data = opensky.get_all_flights()
        
        if 'error' in data:
            if data['error'] == 'rate_limit':
                return jsonify({
                    'success': False,
                    'error': 'rate_limit',
                    'retry_after': data.get('retry_after', 60)
                }), 429
            else:
                return jsonify({'success': False, 'error': data['error']}), 500
        
        return jsonify(data)
    except Exception as e:
        print(f"❌ Ошибка получения рейсов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flight/<icao24>')
@login_required
def get_flight(icao24):
    """API endpoint для детальной информации о конкретном рейсе"""
    try:
        details = opensky.get_flight_details(icao24)
        track = opensky.get_track(icao24)
        
        return jsonify({
            'success': True,
            'details': details,
            'track': track
        })
    except Exception as e:
        print(f"❌ Ошибка получения деталей рейса: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Статистика по самолётам в реальном времени"""
    try:
        data = opensky.get_all_flights()
        
        if 'success' in data and data['success']:
            flights = data.get('flights', [])
            
            # Подсчёт статистики
            total = len(flights)
            in_air = sum(1 for f in flights if not f.get('on_ground', True))
            on_ground = total - in_air
            
            # Уникальные страны
            countries = set(f.get('country') for f in flights if f.get('country'))
            
            return jsonify({
                'success': True,
                'total': total,
                'in_air': in_air,
                'on_ground': on_ground,
                'countries': len(countries),
                'timestamp': data.get('time', int(datetime.now().timestamp()))
            })
        
        return jsonify({'success': False, 'error': 'Нет данных'})
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health():
    """Endpoint для проверки работоспособности приложения"""
    try:
        db_status = 'connected' if db.engine else 'disconnected'
        opensky_status = 'configured' if Config.OPENSKY_CLIENT_ID else 'not configured'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'opensky': opensky_status,
            'timestamp': datetime.utcnow().isoformat(),
            'environment': 'production' if not Config.DEBUG else 'development'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'success': False, 'error': 'Страница не найдена'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'}), 500

@app.errorhandler(401)
def unauthorized_error(error):
    return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ✈️  SkyTrack Pro - Профессиональный трекер рейсов         ║
    ║                                                              ║
    ║   📍 Адрес: http://localhost:{port}                          ║
    ║   🔄 Обновление: каждые {Config.FLIGHT_UPDATE_INTERVAL} секунд   ║
    ║   🔑 OpenSky: {'✅' if Config.OPENSKY_CLIENT_ID else '❌'}                   ║
    ║   📧 Email: {'✅' if Config.MAIL_USERNAME else '❌'}                    ║
    ║   🗄️  База: {'✅' if Config.SQLALCHEMY_DATABASE_URI else '❌'}           ║
    ║   🗺️  Google Maps: {'✅' if Config.GOOGLE_MAPS_API_KEY else '❌'}        ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG, threaded=True)
